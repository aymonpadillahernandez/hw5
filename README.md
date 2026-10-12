# Campus Customs: multi-agent operations desk

Homework 5, MGT 409 *AI for Managers* (Yale SOM, Fall 2026).

Campus Customs is a small Yale merchandise shop. Five specialist agents resolve its business tickets: Boss, Inventory, Accounting, Facilities and Customer Service. They read the shop database only through a shared MCP server, delegate work to each other, and hand every payment to a person, who approves it on a React dashboard. Every agent runs on `gpt-6-luna` through Portkey, and every step of every run is written to an append-only audit trail.

```
Dashboard (React + Vite, :5173)  ->  FastAPI backend (:8000)  ->  agent team (PydanticAI)
                                         |                            |
                                         |  approve / reset           |  read-only MCP tools
                                         v                            v
                                 data/campus_customs_new.db  <-  MCP server (FastMCP, stdio)
```

The full design is in [`output/harness.md`](output/harness.md): tables, tools, agents, audit trail, safety rules, token limits and routes.

## Project structure

| Path | What it holds |
|---|---|
| `data/campus_customs.db` | The original database. It is never written. |
| `data/campus_customs_new.db` | The working database. Agents read it; only approvals and resets write it. It is committed in its state after the final run. |
| `mcp_server/` | `server.py` is the FastMCP server `campus-customs-ops`, with 14 read-only tools. `models.py` holds the tool result types. |
| `backend/` | `main.py` is the FastAPI app and `models.py` the shared data types. The 5 agents are in `agents/` and their prompts in `prompts/`. Also: `config.py` (model and limits), `mcp_link.py` (MCP client), `desk.py` (the only code that writes the database), `audit.py` (audit trail) and `run_team.py` (CLI). |
| `frontend/` | The React + TypeScript dashboard. |
| `output/` | Harness, audit trail, ticket plan and results, resolved-board screenshots, design notes, MCP smoke test, repo URL. |
| `scripts/`, `tests/` | Report builders (`resolved_report.py`, `resolved_board.py`) and the MCP smoke test. |
| `.mcp.json` | Registers the MCP server for Claude Code (the "vibe coder"). |

## Setup (once)

You need Python 3.12 or newer (tested on 3.14.7), Node 22 or newer (tested on 24) and a Portkey API key.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env          # then put your real PORTKEY_API_KEY in .env (never commit it)
cd frontend && npm install && cd ..
```

## 1. Copy or reset the original database into the working database

`data/campus_customs.db` is the clean starting point and is never changed. To start from it, copy it over the working database while the backend is stopped:

```bash
cp data/campus_customs.db data/campus_customs_new.db && chmod u+w data/campus_customs_new.db
```

The `chmod` matters because the original may be read-only, and the working copy must stay writable. If the backend is running, use the reset route instead. It copies the original with SQLite's backup API, checks the copy matches, and records the reset in the audit trail:

```bash
curl -X POST http://localhost:8000/api/reset -H 'content-type: application/json' -d '{"confirm": true}'
```

The **Reset data** button at the top of the dashboard does the same thing.

## 2. Start the MCP server

The backend starts the MCP server for you, as a stdio child process, every time it starts. To run it on its own:

```bash
.venv/bin/python mcp_server/server.py          # stdio: waits for an MCP client (Ctrl+C to stop)
.venv/bin/python mcp_server/server.py --http   # HTTP at http://127.0.0.1:8005/mcp
```

`--db PATH` points it at another copy of the database. Claude Code picks it up from `.mcp.json` when a session is opened in this folder: approve `campus-customs-ops` when asked.

## 3. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

The API is at <http://localhost:8000> and its interactive docs are at <http://localhost:8000/docs>. Keep this terminal open.

## 4. Start the React board

In a **second** terminal, keeping the backend running:

```bash
cd frontend
npm run dev
```

Open <http://localhost:5173>. The board calls the backend at `http://localhost:8000`, and the backend allows this origin through CORS.

## 5. Full 3-ticket run from a clean database

1. With the backend running, click **Reset data** on the board (or run the `curl` reset above). Checking should read **$3,400.00** and all 3 tickets should show **Open**.
2. Type your name in **Approving as**.
3. For tickets 101, 102 and 103 in turn: click **Start the team** and watch the agents work live. Then read the Boss's decision and approve the payment or purchase it prepared. If the team prepared nothing, close the ticket without a payment. Approvals are the only way cash changes.
4. Rebuild the reports from the audit trail and the database:

```bash
.venv/bin/python scripts/resolved_report.py   # output/resolved_tickets.json; fails if the cash does not reconcile
.venv/bin/python scripts/resolved_board.py    # output/resolved_board.html + screenshots (needs both servers and Google Chrome)
```

To run the team without the board: `cd backend && ../.venv/bin/python run_team.py --all-open` (or `--ticket 101`).

## Safety in one paragraph

Agents cannot move money or change records:

- **Read-only tools.** The MCP server is read-only and each agent sees only its role's tools.
- **No invented facts.** An answer citing a tool nobody called is sent back to the model.
- **Money needs a person.** Every money action is forced to need human approval. `POST /api/approve` takes the amount from the database, refuses double payments and overdrafts, and is the only route that changes cash.
- **Untrusted text.** Ticket notes are treated as data, never as instructions.
- **Drafts only.** Customer replies are drafts that are never sent.

## Results of the official run (2026-10-12)

All 3 tickets were resolved and checking went from $3,400.00 to $3,128.00, as recorded in `cash_accounts`. See `output/resolved_tickets.json`, `output/resolved_board.html`, and the Expected / Actual / Cash / Reflection tabs in `output/desk_tickets.html`.
