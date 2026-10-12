# Campus Customs operations desk: design choices

The dashboard (`frontend/`, React + Vite + TypeScript) is the human side of the multi-agent system. Five agents work a ticket, and one person reads what they did and approves any money that moves. Every design choice below serves one of three goals: let the person see the agents' work as it happens, trust what they read, and keep control of the cash.

## 1. One screen, read top to bottom

The layout follows the order of a decision. The ticket list sits on the left, with a status pill for each ticket: Open, Agents working, Needs your review or Resolved. On the right, the selected ticket appears as a header card holding the single main button, *Start the team*. Below it come the five agent cards, then the live activity feed, then the Boss's decision. The person never has to look anywhere else.

- **Checking balance stays in view.** It sits top right on every screen and briefly shows the change ("−$840.00 just now") after an approval, so the effect of a click is visible at once.
- **Status speaks in plain words.** The pills say *Needs your review*, not internal codes such as `ready_for_approval`. The same words appear in the ticket list and in the header.
- **The layout adapts.** On a wide screen the five agents sit in one row, with the feed and the decision side by side. On narrower screens they wrap, so nothing scrolls sideways.

## 2. Live activity from the audit trail

The dashboard has no second channel for "live" data. While a team runs, it polls `GET /api/events` once a second (`POLL_MS`) and rebuilds the run from the same `output/audit_trail.json` that records everything for auditors. What the person watches is exactly what is audited. Because the run is rebuilt from the trail, a page reload keeps the run, the decision, approvals and closures. A reset starts clean, because runs and approvals from before the last reset are ignored.

- **Agent cards show each agent's state.** Each card reads *Waiting*, *Working* (with a pulsing ring and its current step, e.g. "Calling get_inventory_for_sku_size"), *Done* (with its short summary) or *Not needed*. The cards also show who asked whom, the MCP tools each agent used and its tokens. Parallel delegations show up as several cards working at once.
- **The feed is a readable timeline.** Hand-offs ("Boss → Inventory") are tinted blue, answers green, and guardrail fixes or refusals amber. Delegated agents are indented by depth. Tool calls are shown with their exact arguments, and tool results are folded away until clicked.
- **No hidden reasoning is shown.** The feed shows tool calls, results and answers, never the model's hidden reasoning, which the backend does not store either.

## 3. A person approves every dollar

Agents only prepare actions. A payment or purchase gets an Approve button only when the agents filled in its structured fields: `approval_kind` plus the invoice, lease or vendor ids. The button names the action and the expected amount ("Pay invoice · $840.00"). Clicking it asks for confirmation, and `POST /api/approve` then charges the amount on record in the database, never a typed one.

- **Approvals are signed.** "Approving as" holds the person's name, saved in the browser, and every approval and closure carries it into the `payments` row and the audit trail.
- **Results are concrete.** An approved action turns green with the payment number and the balance before and after. Errors such as "Not enough cash" appear inline on the action and change nothing.
- **Resolution is explicit.** The last approval for a ticket resolves it in the same transaction. A ticket that needs no payment, such as a declined discount, is closed with *Close ticket without a payment*. A resolved ticket shows a green banner and cannot be rerun until the data is reset.

## 4. Trust cues

The decision panel puts the Boss's summary first and the proposed actions second. A customer reply draft follows, labelled *never sent automatically*, with a copy button. The facts sit in a fold, each tagged with the MCP tool that returned it and the table that tool reads. Open questions and facts missing from the database are listed rather than hidden.

- **Unused agents are shown as unused.** An agent the Boss skipped is greyed out as *Not needed*, so it is clear the plan was deliberate, not broken.
- **Actions that move no money stay text.** "Confirm the email with the landlord" says *Needs a person, but no money moves in the dashboard* instead of offering a fake button.

## 5. Visual language

The look is Apple-style: a light grey canvas, white cards with 16–18 px corners and soft shadows, the system font, and tabular numbers for money. Yale blue (`#00356b`) is reserved for brand and primary actions. Each agent has one fixed colour, the same one used in `desk_tickets.html`:

| Agent | Colour |
|---|---|
| Boss | Yale blue |
| Inventory | Teal |
| Accounting | Green |
| Facilities | Amber |
| Customer Service | Raspberry |

Body text in summaries and reasons is justified. Icons are small inline SVGs, so the page loads no external fonts, icon sets or images.

## 6. How it connects

The frontend calls the backend directly at `http://localhost:8000` (`API_BASE` in `src/api.ts`; `VITE_API_BASE` can override it). The backend allows the Vite origin `http://localhost:5173` through CORS (`FRONTEND_ORIGINS`). Start the backend with `uvicorn main:app --reload --port 8000` from `backend/` and the dashboard with `npm run dev` from `frontend/`.

Tested on 2026-10-12:

- **Live run:** ticket 101 run live from the dashboard (51,753 tokens). The agent cards and feed updated each second, and the decision appeared with one prepared stock purchase.
- **Approval:** approving it moved checking from $3,400.00 to $3,392.00 and resolved the ticket. A reload kept everything; Reset restored $3,400.00 and three open tickets.
- **Clean checks:** no console errors, no failed requests, no server errors. The production build and the TypeScript check pass.
