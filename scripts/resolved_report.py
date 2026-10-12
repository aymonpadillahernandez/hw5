"""Build output/resolved_tickets.json from what really happened: the audit trail and the working database.

For every ticket it takes the latest agent run after the last reset, then records who the Boss called first, every
delegation, the MCP tools each agent used, each agent's summary, the Boss's decision and the approvals a person
made. The cash section starts from the balance the reset recorded and must end at the real balance in
cash_accounts. Read-only: it never writes the database or the audit trail.

    .venv/bin/python scripts/resolved_report.py --audit output/audit_trail.json --db data/campus_customs_new.db \
        --out output/resolved_tickets.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASH_ACCOUNT = "checking"


def ordered_unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def ticket_report(events: list[dict], ticket: dict, approvals: list[dict], closures: list[dict]) -> dict:
    run = [e for e in events if e["run_id"] == events[0]["run_id"]] if events else []
    end = next((e for e in run if e["kind"] == "run_end"), None)
    boss_batches = [e for e in run if e["agent"] == "boss" and e["kind"] == "model_response"
                    and any(c["tool"] == "delegate" for c in e["details"]["tool_calls"])]
    first = [c["args"].get("to_agent") for c in boss_batches[0]["details"]["tool_calls"] if c["tool"] == "delegate"] \
        if boss_batches else []
    tools: dict[str, list[dict]] = {}
    for e in run:
        if e["kind"] == "model_response":
            for c in e["details"]["tool_calls"]:
                if c["tool"] != "delegate":
                    tools.setdefault(e["agent"], []).append({"tool": c["tool"], "args": c["args"]})
    summaries: dict[str, list[str]] = {}
    for e in run:
        if e["kind"] == "end":
            summaries.setdefault(e["agent"], []).append(e["details"].get("summary", ""))
    tokens = {}
    for e in run:
        if e["kind"] == "agent_end" and e.get("usage"):
            tokens[e["agent"]] = tokens.get(e["agent"], 0) + e["usage"]["input_tokens"] + e["usage"]["output_tokens"]
    resolved_by = next((f"approval of payment {a['payment_id']} by {a['approved_by']}" for a in approvals
                        if a.get("ticket_status") == "resolved"), None)
    if resolved_by is None and closures:
        resolved_by = f"closed without a payment by {closures[-1]['resolved_by']}"
    return {
        "ticket_id": ticket["id"], "type": ticket["type"], "requester": ticket["requester"], "subject": ticket["subject"],
        "status_in_db": ticket["status"], "resolved_by": resolved_by,
        "run": {
            "run_id": run[0]["run_id"] if run else None,
            "started_at": run[0]["time"] if run else None,
            "finished_at": end["time"] if end else None,
            "seconds": round((datetime.fromisoformat(end["time"]) - datetime.fromisoformat(run[0]["time"])).total_seconds(), 1)
            if end else None,
            "stop_reason": end["details"]["stop_reason"] if end else "no run_end",
            "team_totals": end["details"]["team_totals"] if end else None,
            "tokens_by_agent": tokens,
        },
        "boss_called_first": first,
        "boss_first_calls_in_parallel": len(first) > 1,
        "delegations": [{"from": e["agent"], "to": e["details"]["to_agent"], "depth": e["depth"], "task": e["details"]["task"]}
                        for e in run if e["kind"] == "delegation"],
        "delegations_refused": [{"from": e["agent"], "to": e["details"]["to_agent"], "reason": e["details"]["reason"]}
                                for e in run if e["kind"] == "delegation_refused"],
        "guardrail_events": [e["details"] for e in run if e["kind"] == "guardrail"],
        "mcp_tools_by_agent": {agent: ordered_unique([c["tool"] for c in calls]) for agent, calls in tools.items()},
        "mcp_calls": tools,
        "agent_summaries": summaries,
        "decision": end["details"].get("output") if end else None,
        "approvals": approvals,
        "closures": closures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the final ticket results from the audit trail and database.")
    parser.add_argument("--audit", type=Path, default=ROOT / "output" / "audit_trail.json")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "campus_customs_new.db")
    parser.add_argument("--out", type=Path, default=ROOT / "output" / "resolved_tickets.json")
    args = parser.parse_args()
    for path in (args.audit, args.db):
        if not path.is_file():
            print(f"Error: not found: {path}", file=sys.stderr)
            return 1
    entries = json.loads(args.audit.read_text(encoding="utf-8"))
    resets = [e for e in entries if e["agent"] == "human" and e["kind"] == "reset"]
    if not resets:
        print("Error: no reset in the audit trail; reset before the full run so the starting balance is known.", file=sys.stderr)
        return 1
    reset = resets[-1]
    after = [e for e in entries if e["time"] > reset["time"]]

    conn = sqlite3.connect(f"{args.db.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    tickets = [dict(r) for r in conn.execute("SELECT id, type, requester, subject, status FROM tickets ORDER BY id")]
    db_balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()[0]
    payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]
    conn.close()

    approvals = [e["details"] | {"time": e["time"]} for e in after if e["agent"] == "human" and e["kind"] == "human_approval"]
    closures = [e["details"] | {"time": e["time"]} for e in after if e["agent"] == "human" and e["kind"] == "ticket_resolved"]
    reports = []
    for t in tickets:
        starts = [e for e in after if e["kind"] == "run_start" and e["ticket_id"] == t["id"]]
        run_events = [e for e in after if starts and e["run_id"] == starts[-1]["run_id"]]
        reports.append(ticket_report(run_events, t, [a for a in approvals if a["ticket_id"] == t["id"]],
                                     [c for c in closures if c["ticket_id"] == t["id"]]))

    start_balance = reset["details"]["cash_balance"]
    changes = [{"ticket_id": a["ticket_id"], "payment_id": a["payment_id"], "kind": a["kind"], "amount": a["amount"],
                "balance_before": a["cash_before"], "balance_after": a["cash_after"], "approved_by": a["approved_by"],
                "what": a["changes"][2] if len(a["changes"]) > 2 else a["changes"][0]} for a in approvals]
    computed_end = round(start_balance - sum(c["amount"] for c in changes), 2)
    totals = {k: sum((r["run"]["team_totals"] or {}).get(k, 0) for r in reports)
              for k in ("requests", "input_tokens", "output_tokens", "total_tokens", "delegations", "mcp_calls")}
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database": f"data/{args.db.name}",
        "reset": {"time": reset["time"], "matches_original": reset["details"]["matches_original"]},
        "all_resolved": all(t["status"] == "resolved" for t in tickets),
        "cash": {
            "account": CASH_ACCOUNT, "starting_balance": start_balance, "changes": changes,
            "total_paid_out": round(sum(c["amount"] for c in changes), 2),
            "ending_balance_computed": computed_end, "ending_balance_in_cash_accounts": db_balance,
            "matches_cash_accounts": abs(computed_end - db_balance) < 0.005,
            "payments_rows_in_db": len(payments),
        },
        "totals": totals,
        "tickets": reports,
        "audit_trail": {"file": "output/audit_trail.json", "total_entries": len(entries),
                        "entries_since_reset": len(after),
                        "run_ids": [r["run"]["run_id"] for r in reports]},
    }
    if not result["cash"]["matches_cash_accounts"]:
        print(f"Error: computed ending balance {computed_end} != cash_accounts {db_balance}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: {len(reports)} tickets, all resolved: {result['all_resolved']}, "
          f"cash {start_balance:,.2f} -> {db_balance:,.2f} (matches cash_accounts)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
