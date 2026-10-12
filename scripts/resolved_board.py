"""Screenshot the resolved dashboard and build output/resolved_board.html around the pictures.

Needs the backend (port 8000) and the dashboard (npm run dev, port 5173) running. It uses the installed Google Chrome
(channel="chrome"), so no browser download is needed. Captions come from output/resolved_tickets.json (written by
scripts/resolved_report.py), and the page checks each ticket shows as Resolved before it takes the picture.

    .venv/bin/python scripts/resolved_board.py --url http://localhost:5173 --data output/resolved_tickets.json \
        --out-dir output/resolved_board_images --html output/resolved_board.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
VIEWPORT = {"width": 1440, "height": 1100}
SCALE = 2  # retina screenshots
SETTLE_MS = 600  # let the selection outline finish its 0.2 s transition before each picture
DECISION = {"ready_for_approval": "Ready for approval", "needs_more_info": "Needs more info", "decline": "Decline",
            "escalate_to_human": "Escalate to a person"}


def usd(n: float) -> str:
    return f"${n:,.2f}"


def capture(url: str, out_dir: Path, ticket_ids: list[int], approver: str | None) -> list[tuple[str, str]]:
    """Return (file name, what it shows) for each screenshot."""
    shots = []
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
        if approver:
            page.add_init_script(f"localStorage.setItem('campus-customs-approver', {json.dumps(approver)})")
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector(".ticket-card")
        page.wait_for_function("document.querySelectorAll('.ticket-card .phase.resolved').length === %d" % len(ticket_ids),
                               timeout=15000)
        for i, tid in enumerate(ticket_ids):
            page.locator(".ticket-card").nth(i).click()
            page.wait_for_selector(".decision-pill")
            page.wait_for_selector(".banner.success")
            page.mouse.move(0, 0)
            page.evaluate("() => { window.scrollTo(0, 0) }")
            page.wait_for_timeout(SETTLE_MS)
            name = f"{i + 1:02d}_ticket_{tid}_resolved.png"
            page.screenshot(path=str(out_dir / name), full_page=True)
            shots.append((name, f"ticket {tid}"))
        page.locator(".ticket-card").nth(0).click()
        page.wait_for_selector(".banner.success")
        page.mouse.move(0, 0)
        page.wait_for_timeout(SETTLE_MS)
        name = f"{len(ticket_ids) + 1:02d}_board_top.png"
        page.screenshot(path=str(out_dir / name), clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": 520})
        shots.append((name, "board"))
        browser.close()
    return shots


def build_html(data: dict, shots: list[tuple[str, str]], images_rel: str) -> str:
    cash = data["cash"]
    by_id = {t["ticket_id"]: t for t in data["tickets"]}
    figures = []
    for name, what in sorted(shots, key=lambda s: s[1] != "board"):  # overview first, then each ticket
        if what == "board":
            caption = (f"<strong>The board after the run.</strong> All {len(by_id)} tickets show <em>Resolved</em> in the list, and the "
                       f"checking balance reads {usd(cash['ending_balance_in_cash_accounts'])}, the value in <code>cash_accounts</code>.")
        else:
            t = by_id[int(what.split()[1])]
            d = t["decision"] or {}
            pay = "; ".join(f"Payment #{a['payment_id']} ({a['kind'].replace('_', ' ')}, {usd(a['amount'])}) approved by "
                            f"{html.escape(a['approved_by'])}, cash {usd(a['cash_before'])} → {usd(a['cash_after'])}"
                            for a in t["approvals"]) or (
                f"Closed without a payment by {html.escape(t['closures'][-1]['resolved_by'])}" if t.get("closures") else "No payment")
            consulted = ", ".join(x.replace("_", " ").title() for x in d.get("agents_consulted", []))
            caption = (f"<strong>Ticket {t['ticket_id']} · {html.escape(t['subject'])}: resolved.</strong> "
                       f"Decision <em>{DECISION.get(d.get('decision'), d.get('decision'))}</em>; the Boss consulted {consulted}. "
                       f"{pay}. Run <code>{t['run']['run_id']}</code>, {t['run']['seconds']} s, "
                       f"{t['run']['team_totals']['total_tokens']:,} tokens.")
        figures.append(f'<figure><img src="{images_rel}/{name}" alt="{html.escape(alt_text(what))}">'
                       f"<figcaption>{caption}</figcaption></figure>")
    closed = [t for t in data["tickets"] if not t["approvals"] and t.get("closures")]
    rows = "".join(f"<tr><td>{c['ticket_id']}</td><td>#{c['payment_id']} · {c['kind'].replace('_', ' ')}</td>"
                   f"<td class='num'>−{usd(c['amount'])}</td><td class='num'>{usd(c['balance_after'])}</td></tr>"
                   for c in cash["changes"]) + "".join(
        f"<tr><td>{t['ticket_id']}</td><td>closed without a payment</td><td class='num'>$0.00</td><td class='num'></td></tr>" for t in closed)
    tot = data["totals"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campus Customs · Resolved board</title>
<style>
  :root {{ --yale: #00356b; --ink: #1d1d1f; --muted: #6e6e73; --line: #e3e3e8; --bg: #f5f5f7; --green: #1f8a4c; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink);
         font: 16px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif; }}
  .wrap {{ max-width: 1120px; margin: 0 auto; padding: 36px 24px 64px; }}
  header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 22px; }}
  .mark {{ width: 52px; height: 52px; border-radius: 14px; background: var(--yale); color: #fff; display: grid; place-items: center;
          font: 700 20px/1 Georgia, serif; }}
  h1 {{ margin: 0; font-size: 28px; letter-spacing: -.02em; }}
  .sub {{ margin: 2px 0 0; color: var(--muted); }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }}
  .kpi {{ background: #fff; border-radius: 16px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  .kpi dt {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }}
  .kpi dd {{ margin: 2px 0 0; font-size: 26px; font-weight: 700; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }}
  .kpi dd.ok {{ color: var(--green); }}
  .card {{ background: #fff; border-radius: 18px; padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,.06); margin-bottom: 22px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ text-align: left; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; padding: 0 0 8px; border-bottom: 1px solid var(--line); }}
  td {{ padding: 9px 0; border-bottom: 1px solid #f0f0f3; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  figure {{ margin: 0 0 28px; background: #fff; border-radius: 18px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 10px 30px rgba(0,0,0,.05); }}
  figure img {{ display: block; width: 100%; height: auto; border-bottom: 1px solid var(--line); }}
  figcaption {{ padding: 14px 20px; font-size: 14px; text-align: justify; hyphens: auto; }}
  code {{ font: 13px "SF Mono", Menlo, monospace; background: #f0f0f4; padding: 1px 6px; border-radius: 6px; }}
  p {{ text-align: justify; }}
  footer {{ color: var(--muted); font-size: 13px; text-align: center; }}
  @media (max-width: 760px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
</style>
</head>
<body>
<div class="wrap">
  <header><div class="mark" aria-hidden="true">CC</div>
    <div><h1>Resolved board</h1>
      <p class="sub">The operations dashboard after the full run of tickets 101, 102 and 103 ({data['reset']['time'][:10]}, starting from a fresh reset).</p></div></header>
  <section class="kpis">
    <div class="kpi"><dt>Tickets resolved</dt><dd class="ok">{sum(1 for t in data['tickets'] if t['status_in_db'] == 'resolved')} / {len(data['tickets'])}</dd></div>
    <div class="kpi"><dt>Starting balance</dt><dd>{usd(cash['starting_balance'])}</dd></div>
    <div class="kpi"><dt>Ending balance</dt><dd>{usd(cash['ending_balance_in_cash_accounts'])}</dd></div>
    <div class="kpi"><dt>Team tokens</dt><dd>{tot['total_tokens']:,}</dd></div>
  </section>
  <section class="card">
    <p>Each ticket was run once through the agent team (Boss first) from the dashboard. A ticket was resolved by approving the payment or purchase the agents prepared, or closed without a payment when they prepared none. The ending balance, {usd(cash['ending_balance_in_cash_accounts'])}, is the real value in <code>cash_accounts</code> ({usd(cash['starting_balance'])} − {usd(cash['total_paid_out'])}). Details are in <code>output/resolved_tickets.json</code>, and every step of every run is in <code>output/audit_trail.json</code>.</p>
    <table><thead><tr><th>Ticket</th><th>Payment</th><th class="num">Amount</th><th class="num">Balance after</th></tr></thead><tbody>{rows}</tbody></table>
  </section>
  {''.join(figures)}
  <footer>Screenshots taken with <code>scripts/resolved_board.py</code> (Playwright, Google Chrome, {VIEWPORT['width']} px wide at {SCALE}×). Captions are generated from <code>output/resolved_tickets.json</code>.</footer>
</div>
</body>
</html>
"""


def alt_text(what: str) -> str:
    return "Dashboard top: three resolved tickets and the checking balance" if what == "board" \
        else f"Dashboard with {what} resolved: agent cards, live activity and decision"


def main() -> int:
    parser = argparse.ArgumentParser(description="Screenshot the resolved dashboard into output/resolved_board.html.")
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument("--data", type=Path, default=ROOT / "output" / "resolved_tickets.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "output" / "resolved_board_images")
    parser.add_argument("--html", type=Path, default=ROOT / "output" / "resolved_board.html")
    args = parser.parse_args()
    if not args.data.is_file():
        print(f"Error: {args.data} not found; run scripts/resolved_report.py first.", file=sys.stderr)
        return 1
    data = json.loads(args.data.read_text(encoding="utf-8"))
    if not data.get("all_resolved"):
        print("Error: not every ticket is resolved yet.", file=sys.stderr)
        return 1
    try:
        approver = next((a["approved_by"] for t in data["tickets"] for a in t["approvals"]), None)
        shots = capture(args.url, args.out_dir, [t["ticket_id"] for t in data["tickets"]], approver)
    except PlaywrightError as exc:
        print(f"Error: could not capture the dashboard at {args.url} (is it running with the backend?): {exc}", file=sys.stderr)
        return 1
    rel = Path(args.out_dir).resolve().relative_to(Path(args.html).resolve().parent).as_posix()
    args.html.write_text(build_html(data, shots, rel), encoding="utf-8")
    print(f"wrote {args.html} with {len(shots)} screenshots in {args.out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
