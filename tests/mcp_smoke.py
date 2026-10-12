"""Smoke-test the Campus Customs MCP server through the vibe coder (Claude Code) and save the evidence.

For each tool, Claude Code runs headless from the project root with only the servers in .mcp.json and no built-in
tools, so the answer can only come from the MCP tool. The tool call and its raw output are taken from Claude Code's
own event stream, then every value is checked against data/campus_customs_new.db.

With --transcript, the tools were already called in an interactive Claude Code session: each tool's latest call, its
raw output and the prompt that triggered it are read from that session's transcript (.jsonl) instead.

    .venv/bin/python tests/mcp_smoke.py --claude PATH_TO_CLAUDE --out output/mcp_smoke.json
    .venv/bin/python tests/mcp_smoke.py --transcript PATH_TO_SESSION.jsonl --out output/mcp_smoke.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_CONFIG = ROOT / ".mcp.json"
DB_PATH = ROOT / "data" / "campus_customs_new.db"
SERVER = "campus-customs-ops"
VIBE_MODEL = "sonnet"
RUN_TIMEOUT_SECONDS = 180

CASES = [
    {"ticket": 101, "tool": "get_inventory_for_sku_size",
     "prompt": "Use the get_inventory_for_sku_size tool from our campus-customs-ops MCP server to check the stock of "
               "SKU CC-TEE-WHITE in size S for ticket 101. Show me exactly what the tool returned.",
     "query": "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
     "params": ("CC-TEE-WHITE", "S")},
    {"ticket": 102, "tool": "get_lease_details",
     "prompt": "Use the get_lease_details tool from our campus-customs-ops MCP server to read lease 1 for ticket 102. "
               "Show me exactly what the tool returned.",
     "query": "SELECT id AS lease_id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
     "params": (1,)},
    {"ticket": 103, "tool": "get_product_pricing",
     "prompt": "Use the get_product_pricing tool from our campus-customs-ops MCP server to read the pricing of SKU "
               "CC-HOOD-NAVY for ticket 103. Show me exactly what the tool returned.",
     "query": "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
     "params": ("CC-HOOD-NAVY",)},
]


def ask_vibe_coder(claude: str, prompt: str, tool: str) -> dict:
    """Run one headless Claude Code turn and pull the MCP tool call, its output and the reply from the stream."""
    full_name = f"mcp__{SERVER}__{tool}"
    cmd = [claude, "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", VIBE_MODEL,
           "--mcp-config", str(MCP_CONFIG), "--strict-mcp-config", "--tools", "", "--allowedTools", full_name,
           "--setting-sources", "user", "--no-session-persistence"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=RUN_TIMEOUT_SECONDS)
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    run = {"tool_name": None, "tool_input": None, "tool_output": None, "reply": None, "model": None,
           "mcp_status": None}
    call_id = None
    for e in events:
        if e.get("type") == "system" and e.get("subtype") == "init":
            run["model"] = e.get("model")
            run["mcp_status"] = next((s.get("status") for s in e.get("mcp_servers", []) if s.get("name") == SERVER), None)
        for block in (e.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == full_name and call_id is None:
                call_id, run["tool_name"], run["tool_input"] = block.get("id"), block["name"], block.get("input")
            elif block.get("type") == "tool_result" and block.get("tool_use_id") == call_id and call_id:
                run["tool_output"] = parse_output(block.get("content"))
        if e.get("type") == "result":
            run["reply"] = e.get("result")
    if proc.returncode != 0 and not run["reply"]:
        run["error"] = (proc.stderr or proc.stdout)[-500:]
    return run


def parse_output(content: object) -> object:
    """A tool_result's content as JSON when it parses, else as the raw text."""
    text = "".join(c.get("text", "") for c in content if isinstance(c, dict)) if isinstance(content, list) else str(content)
    try:
        return json.loads(text)
    except ValueError:
        return text


def read_transcript(path: Path) -> tuple[dict, dict]:
    """Each tool's latest call in an interactive session: prompt typed before it, input, raw output, model, time."""
    prefix = f"mcp__{SERVER}__"
    calls, prompt, meta = {}, None, {}
    for line in path.read_text(encoding="utf-8").splitlines():
        e = json.loads(line) if line.strip().startswith("{") else {}
        if e.get("cwd") and "started_in" not in meta:
            meta["started_in"] = e["cwd"]  # the folder whose .mcp.json the session loaded
        message = e.get("message") or {}
        content = message.get("content")
        if e.get("type") == "user" and isinstance(content, str) and not content.lstrip().startswith("<"):
            prompt = content.strip()
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name", "").startswith(prefix):
                calls[block["id"]] = {"tool": block["name"].removeprefix(prefix), "tool_name": block["name"],
                                      "tool_input": block.get("input"), "prompt": prompt,
                                      "called_at": e.get("timestamp"), "tool_output": None}
                meta |= {"app": f"{e.get('version')} (Claude Code)", "model": message.get("model"),
                         "session_id": e.get("sessionId")}
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                calls[block["tool_use_id"]]["tool_output"] = parse_output(block.get("content"))
    latest = {c["tool"]: c for c in calls.values() if c["tool_output"] is not None}  # later calls overwrite earlier
    return latest, meta


def db_row(query: str, params: tuple) -> dict | None:
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(query, params).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def compare(output: object, row: dict | None) -> tuple[bool, list[str]]:
    """Every database column must appear in the tool output with the same value, and found must be true."""
    if not isinstance(output, dict) or row is None:
        return False, ["tool output is not a JSON object" if row else "row missing from the database"]
    problems = [f"{k}: tool {output.get(k)!r} vs db {v!r}" for k, v in row.items() if output.get(k) != v]
    if output.get("found") is not True:
        problems.append("found is not true")
    return not problems, problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the MCP tools through Claude Code.")
    parser.add_argument("--claude", default=shutil.which("claude") or "claude", help="path to the claude CLI")
    parser.add_argument("--transcript", type=Path,
                        help="read the calls from an interactive Claude Code session transcript (.jsonl) instead")
    parser.add_argument("--out", type=Path, default=ROOT / "output" / "mcp_smoke.json")
    args = parser.parse_args()
    if args.transcript and not args.transcript.is_file():
        print(f"Error: transcript not found at {args.transcript}", file=sys.stderr)
        return 1
    if not args.transcript and not Path(args.claude).is_file() and not shutil.which(args.claude):
        print(f"Error: claude CLI not found at {args.claude}; pass --claude PATH", file=sys.stderr)
        return 1
    for need in (MCP_CONFIG, DB_PATH):
        if not need.is_file():
            print(f"Error: missing {need.relative_to(ROOT)}", file=sys.stderr)
            return 1
    if args.transcript:
        session_calls, vibe_coder = read_transcript(args.transcript)
        vibe_coder["how"] = ("interactive Claude Code session; each tool called natively from the user's prompt, "
                             "output copied verbatim from the session transcript")
    else:
        version = subprocess.run([args.claude, "--version"], capture_output=True, text=True).stdout.strip()
    results = []
    for case in CASES:
        if args.transcript:
            run = session_calls.get(case["tool"], {"prompt": None, "tool_name": None, "tool_input": None,
                                                   "tool_output": None, "error": "tool not called in this session"})
        else:
            print(f"ticket {case['ticket']}: asking the vibe coder to call {case['tool']}...", file=sys.stderr)
            run = ask_vibe_coder(args.claude, case["prompt"], case["tool"])
            vibe_coder = {"app": version, "model": run.get("model"), "mcp_server_status": run.get("mcp_status"),
                          "how": "headless Claude Code from the project root, servers from .mcp.json only, "
                                 "no built-in tools"}
        row = db_row(case["query"], case["params"])
        ok, problems = compare(run["tool_output"], row)
        results.append({"ticket": case["ticket"], "prompt": run.get("prompt") or case["prompt"],
                        "tool_name": case["tool"], "mcp_tool_called": run["tool_name"],
                        "tool_input": run["tool_input"], "tool_output": run["tool_output"],
                        **({"called_at": run["called_at"]} if run.get("called_at") else {}),
                        **({"vibe_coder_reply": run["reply"]} if "reply" in run else {}),
                        "db_check": {"query": case["query"], "params": list(case["params"]), "db_row": row,
                                     "matches": ok, "problems": problems},
                        **({"error": run["error"]} if run.get("error") else {})})
    connection = {"config_file": ".mcp.json", "server": SERVER, **json.loads(MCP_CONFIG.read_text())["mcpServers"][SERVER]}
    started_in = vibe_coder.pop("started_in", None)
    if started_in and Path(started_in).resolve() == ROOT.parent:
        connection["loaded_by_this_session_from"] = ("the workspace folder's .mcp.json, one level above the project "
                                                     "(same mcp_server/server.py and .venv, absolute paths)")
    elif started_in:
        connection["loaded_by_this_session_from"] = ".mcp.json at the project root"
    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vibe_coder": vibe_coder,
        "connection": connection,
        "database": f"data/{DB_PATH.name}",
        "all_outputs_match_db": all(r["db_check"]["matches"] for r in results),
        "tests": results,
    }
    if not any(r["tool_output"] for r in results):
        print("Error: no tool output captured; output file not written", file=sys.stderr)
        print(json.dumps(results, indent=2)[:2000], file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}; "
          f"all match: {evidence['all_outputs_match_db']}", file=sys.stderr)
    return 0 if evidence["all_outputs_match_db"] else 2


if __name__ == "__main__":
    sys.exit(main())
