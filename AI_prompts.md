# AI Prompts — Homework 5

**Started:** 2026-10-11 23:16 (local time). The prompt-log audit checks every prompt typed from then on.

This file is the log of what I type to the AI while vibe-coding Homework 5. Prompts are recorded verbatim, numbered in the order I typed them. Sections for each problem are added as we reach them.

## Problem 1: Vibe coder prompts

### Problem number & title

Problem 1: Vibe coder prompts

### Prompt(s) used

**#1**
> are you ready to start working on HW5?

**#2**
> let's move to problem 1: vibe coder prompts
>
> before we start let's keep in mind what we are building in this homework
>
> a Campus Customs multi-agent operations system where different specialist agents will work together, use shared tools through an mcp server, work with the shop database and resolve 3 business tickets through a dashboard
>
> the final project will be submitted as a public GitHub repository
>
> create "AI_prompts.md" at the start of the assignment and keep it updated as we work using the skill created a few weeks ago

### Follow-up prompts

No follow-up prompt used.

## Problem 2: Study the Campus Customs database

### Problem number & title

Problem 2: Study the Campus Customs database

### Prompt(s) used

**#3**
> let's move to problem 2: study the campus customs database
>
> you have the file "data.zip" in the HW5 folder, unzip it when necessary
>
> open "data/campus_customs.db" and study every table and field
>
> create "data/campus_customs_new.db" as a copy of the original database
>
> keep "data/campus_customs.db" unchanged and use "data/campus_customs_new.db" as our working database from now on
>
> review the 3 open tickets in the "tickets" table
>
> start "output/harness.md" and include
> -every table in the database
> -the fields in each table
> -one short line explaining why each table matters to Campus Customs

### Follow-up prompts

No follow-up prompt used.

## Problem 3: Build the MCP server

### Problem number & title

Problem 3: Build the MCP server

### Prompt(s) used

**#4**
> let's move to problem 3: build the mcp server
>
> build an MCP server inside "mcp_server/" using FastMCP
>
> the server should use "data/campus_customs_new.db"
>
> create these 3 clearly named tools based on the open tickets
>
> -"get_inventory_for_sku_size" should read the inventory information needed for ticket 101
> -"get_lease_details" should read the lease information needed for ticket 102
> -"get_product_pricing" should read the pricing information needed for ticket 103
>
> only return information that exists in the database and never invent any data
>
> we don't need to connect or run the MCP server yet
>
> update "output/harness.md" for each tool with
> -the tool name
> -the table it reads
> -the ticket it helps unlock
> -one short sentence explaining why it is the right tool for that ticket
>
> also create "mcp_server/README.md" explaining
> -what the MCP server is for
> -which database file it uses
> -the 3 tools it currently has
>
> don't forget to confirm that everything we've done before is working fine before moving to the new problem

### Follow-up prompts

No follow-up prompt used.

## Problem 4: Add the MCP server to vibe coder and test each tool

### Problem number & title

Problem 4: Add the MCP server to vibe coder and test each tool

### Prompt(s) used

**#5**
> let's move to problem 4: add the mcp server to vibe coder and test each tool
>
> connect the MCP server we built to this project so our vibe coder can call its tools
>
> save the connection JSON in ".mcp.json" at the project root, or use the equivalent local MCP server configuration if our vibe coder saves it differently
>
> once connected test each of our 3 MCP tools
>
> save the evidence in "output/mcp_smoke.json"
>
> for each tool include
> -the prompt we asked the vibe coder
> -the tool name
> -the tool output
>
> make sure every tool output matches the real values in "data/campus_customs_new.db"

### Follow-up prompts

**#6**
> give me step by step guide to fulfill your demand of "open a new Claude Code session from the same workspace folder as this one"

**What was lacking after the first prompt:** The MCP server only loads when a session starts, so the tools could not be tested in the session that connected it; the AI asked for a new session without explaining how to open one, so this prompt asked for step-by-step instructions.

**#7**
> Problem 4 test 1 (ticket 101): use the campus-customs-ops MCP tool get_inventory_for_sku_size to check SKU CC-TEE-WHITE in size S and show me exactly what it returned

**What was lacking after the first prompt:** The tools could only be called from a new session, so each of the 3 tools had to be tested with its own prompt there; this one tests `get_inventory_for_sku_size` for ticket 101.

**#8**
> Problem 4 test 2 (ticket 102): use the campus-customs-ops MCP tool get_lease_details to read lease 1 and show me exactly what it returned

**What was lacking after the first prompt:** Each of the 3 tools needed its own test prompt in the new session; this one tests `get_lease_details` for ticket 102.

**#9**
> Problem 4 test 3 (ticket 103): use the campus-customs-ops MCP tool get_product_pricing to read SKU CC-HOOD-NAVY, show me exactly what it returned, then save the 3 tests in output/mcp_smoke.json and check every output against data/campus_customs_new.db

**What was lacking after the first prompt:** The last of the 3 tools still had to be tested in the new session, and the evidence file from the first prompt had not been written yet; this one tests `get_product_pricing` for ticket 103 and asks for `output/mcp_smoke.json` with the database check.

**#10**
> confirm that problem 4 is completed and running properly

**What was lacking after the first prompt:** The tests ran in a second session, so this prompt asked the original session to confirm the evidence; the check found `output/mcp_smoke.json` named the project's `.mcp.json` although that session had loaded the server from the workspace folder's `.mcp.json`, and the file was corrected.

## Problem 5: Build the agent team and grow the MCP tools

### Problem number & title

Problem 5: Build the agent team and grow the MCP tools

### Prompt(s) used

**#11**
> let's move to problem 5: build the agent team and grow the mcp tools
>
> build our Campus Customs agent team using PydanticAI with these 5 roles
>
> -Boss
> -Inventory
> -Accounting
> -Facilities
> -Customer Service
>
> include the prompts, models and agent loops needed so the agents can delegate work to each other with full connectivity
>
> put one prompt file per agent inside "backend/prompts/"
>
> keep the agent files under "backend/" and make sure the 5 roles are clearly separated
>
> put the shared structured data types in "backend/models.py"
>
> use "PORTKEY_API_KEY" and only "gpt-6-luna" for every agent
>
> write each agent prompt in our own words and make it detailed enough to cover that agent's responsibilities, scope and shop rules
>
> review the open tickets and add any additional tools the agents need to the existing MCP server
>
> all shop facts must come through the MCP server using "data/campus_customs_new.db"
>
> do not create another shop tools layer that bypasses the MCP server
>
> make the agents append to "output/audit_trail.json" as they run
>
> for every agent-loop step record enough information so we can audit what happened later
>
> keep the previous entries and don't overwrite the file on each run
>
> update "output/harness.md" with
> -each agent
> -each MCP tool including the new ones
> -the database table used by each tool
> -a short safety section with guardrails for agents working with real customers and real money
> -limits that keep token use under control
>
> update "mcp_server/README.md" so the tool list matches the MCP server we have now

### Follow-up prompts

No follow-up prompt used.

## Problem 6: Plan the three tickets

### Problem number & title

Problem 6: Plan the three tickets

### Prompt(s) used

**#12**
> let's move to problem 6: plan the three tickets
>
> before we run the agents create "output/desk_tickets.html"
>
> create one tab for each open ticket
> -101
> -102
> -103
>
> also add empty "Cash" and "Reflection" tabs for later problems
>
> for each ticket tab fill only an "Expected" section for now and leave room for an "Actual" section that we will complete after running the agents
>
> for each "Expected" section explain in our own words
> -who the Boss should call first and why
> -all the agent delegations we expect for that ticket
> -which MCP tools we expect the agents to use
>
> make the plan specific to each ticket and only involve the agents that are actually needed

### Follow-up prompts

No follow-up prompt used.

## Problem 7: Backend routes

### Problem number & title

Problem 7: Backend routes

### Prompt(s) used

**#13**
> let's move to problem 7: backend routes
>
> in "backend/main.py" use FastAPI and add the routes we need to
>
> -return the 3 tickets and whether each one is open or resolved
> -take a ticket id and run our agent team on that ticket
> -return recent agent events including what each agent said and which tools they used
> -approve a payment or purchase after a human clicks approve, the agents should only prepare it and this route is what actually changes cash
> -return the current checking balance from "cash_accounts"
> -reset the database to the original values when we want a fresh run
>
> make sure the backend runs from "backend/" with "uvicorn main:app --reload --port 8000"
>
> this should make the backend available at "http://localhost:8000"
>
> update "output/harness.md" listing each route in one line with
> -the url
> -what it does

### Follow-up prompts

No follow-up prompt used.

## Problem 8: Agent dashboard

### Problem number & title

Problem 8: Agent dashboard

### Prompt(s) used

**#14**
> let's move to problem 8: agent dashboard
>
> build the frontend dashboard in "frontend/" using React + Vite + TypeScript and connect it to the backend we built in problem 7
>
> the dashboard should
> -show the 3 tickets
> -let us start one ticket
> -show each agent's live activity while they work
> -show when the ticket is resolved
> -show a short summary for each agent
> -let us approve a payment or purchase when human approval is needed
> -show the current checking balance
>
> the frontend should call "http://localhost:8000"
>
> make sure the backend allows the Vite frontend origin, usually "http://localhost:5173"
>
> the frontend should run with
>
> "npm run dev"
>
> create "output/design.md" explaining the main design choices we made for the dashboard

### Follow-up prompts

**#15**
> I run both comands but the website "http://localhost:5173" is not working in Chrome

**What was lacking after the first prompt:** The dashboard worked in the AI's own tests, but it did not open in the user's Chrome after running the two start commands, so this prompt reported the problem.

## Problem 9: Resolve the tickets

### Problem number & title

Problem 9: Resolve the tickets

### Prompt(s) used

**#16**
> it's working now, let's move to problem 9: resolve the tickets
>
> before the full run reset "data/campus_customs_new.db" to the original values and record the starting checking balance
>
> run tickets 101, 102 and 103 through our agent team until they are resolved
>
> in "output/desk_tickets.html" keep the "Expected" section we already created for each ticket and complete the "Actual" section based on what really happened during the run
>
> complete the "Cash" tab with
> -the starting checking balance
> -the cash changes / payments from each ticket
> -the ending checking balance
>
> make sure the ending balance matches the real value in "cash_accounts"
>
> save the final ticket results in "output/resolved_tickets.json"
>
> create "output/resolved_board.html" with screenshots showing the resolved board
>
> make sure the real agent runs are appended to "output/audit_trail.json"
>
> finish "output/harness.md" with the final system information

### Follow-up prompts

No follow-up prompt used.

## Problem 10: Reflection

### Problem number & title

Problem 10: Reflection

### Prompt(s) used

**#17**
> let's move to problem 10: reflection
>
> I want to complete the "Reflection" tab in "output/desk_tickets.html".
>
> for each of the 3 tickets, I want to
> -evaluate how the agent team performed
> -compare what actually happened with what we wrote in the "Expected" section
>
> also I want to propose
> -3 new business problems we could solve with the agents and MCP tools we already have
> -3 business problems we could not solve with the current setup and would require new tools or agents
>
> ask me question by question and record my answers in the reflection tab

### Follow-up prompts

**#18** (answer to the AI's question "Which run should be the official final run for Problem 9 (and the one we reflect on in Problem 10)?")
> Your dashboard session (Recommended)

**What was lacking after the first prompt:** The readiness check found a second session run from the dashboard after Problem 9 (reset, three new runs, ending at $3,128.00), so the Problem 9 files no longer matched `cash_accounts`. This answer chose that dashboard session as the official run to regenerate and reflect on.

**#19** (answer to reflection question 1 of 8)
> overall good result, but not exactly as expected. I expected Inventory to go first and then involve the other agents depending on what it found. Instead, Inventory, Accounting and Customer Service worked almost in parallel. They correctly identified that size S was out of stock and proposed buying 1 unit for $8, which I approved. The main miss was that Accounting did not check the linked $840 invoice 501, which was part of our original plan and remained open after the ticket was resolved.

**What was lacking after the first prompt:** Prompt #17 asked the AI to ask the reflection questions one at a time; this is the answer to question 1, recorded verbatim in the Reflection tab.

**#20**
> delete tge Accounting comment

**What was lacking after the first prompt:** The answer to reflection question 1 said Accounting worked in parallel with the others, but in the official run Accounting was never called; this prompt asked to delete that mention, so the Q1 answer now reads "Inventory and Customer Service worked almost in parallel."

**#21** (answer to the reflection question on ticket 102)
> this was the cleanest one. Facilities was the right agent and checked the landlord, amount, due date and previous payments. The main difference is that I expected Accounting to also check cash and the other open invoice, but it was not involved. The agents also correctly flagged that the email could not be fully verified inside the system.

**What was lacking after the first prompt:** Prompt #17 asked for the reflection one question at a time; this answer covers ticket 102's performance and its comparison with Expected together, so the Reflection tab now asks one combined question per ticket (5 questions in all) and records this answer verbatim under ticket 102.

**#22**
> nono, stop

**What was lacking after the first prompt:** The AI merged each ticket's two reflection questions into one without asking first, so this prompt stopped it.

**#23** (the user's reflection answers for the three tickets)
> ticket 101 - bulldog tee
> overall good result, but not exactly as expected. I expected Inventory to go first and then involve the other agents depending on what it found. Instead, Inventory, Accounting and Customer Service worked almost in parallel. They correctly identified that size S was out of stock and proposed buying 1 unit for $8, which I approved. The main miss was that Accounting did not check the linked $840 invoice 501, which was part of our original plan and remained open after the ticket was resolved. desk_tickets
>
> ticket 102 - rent due
> this was the cleanest one. Facilities was the right agent and checked the landlord, amount, due date and previous payments. The main difference is that I expected Accounting to also check cash and the other open invoice, but it was not involved. The agents also correctly flagged that the email could not be fully verified inside the system. desk_tickets
>
> ticket 103 - bulk hoodie discount
> the agents correctly found that we only had 8 hoodies vs 20 requested and that cost was $22 vs $58 list price. I expected Accounting to propose a bulk price, but the system did not because there was no discount policy or requested target price in the database. I actually think this was a good decision because it avoided inventing a commercial rule. We finally approved purchasing the missing 12 units for $264.

**What was lacking after the first prompt:** After stopping the AI (prompt #22), the user gave the evaluation and the comparison with Expected for each ticket in one message; they are recorded per ticket in the Reflection tab (the stray "desk_tickets" words left out, and the Accounting mention in ticket 101 removed as asked in prompt #20).

**#24**
> those are my answers, confirm that there's no misunderstaing between the tickets

**What was lacking after the first prompt:** The user asked the AI to confirm that each of the three answers was recorded under the right ticket and matched that ticket's run.

**#25** (the user's remaining reflection answers)
> here you have the rest answers, including one that I missed before:
>
> what would have been simpler with one agent + tools?
> -ticket 102 for sure. One agent could have checked the ticket, lease, payments and cash without needing a multi-agent workflow
> -ticket 101 probably as well. One agent could have checked stock, invoice, pricing and cash together and maybe avoided missing invoice 501
> -ticket 103 is where the multi-agent setup made more sense because we needed inventory, pricing and customer communication at the same time
>
> 3 new problems we could solve with the tools we already have:
> -a customer asks for a product or size that is out of stock
> -a vendor asks about an unpaid invoice
> -another rent notice arrives for the current shop
>
> 3 problems we could not solve today
> -define the right bulk discount → we would need a real pricing / margin policy and probably a pricing tool
> -confirm that a vendor can really supply a specific SKU and at what price → we would need vendor availability / quote tools
> -verify an external email or contact the landlord/customer directly → we would need email / CRM tools
>
> confirm there's nothing missing

**What was lacking after the first prompt:** The reflection list had no question on what one agent with tools would have done more simply, so the user added it with an answer, gave the 3 problems the current agents and MCP tools could solve and the 3 they could not, and asked the AI to confirm nothing was missing.

## Problem 11: Submit to GitHub

### Problem number & title

Problem 11: Submit to GitHub

### Prompt(s) used

**#26** (sent with an image of the required project structure, transcribed below)
> let's move to problem 11: submit to github
>
> prepare the final "hw5" project and push it to a public GitHub repository
>
> make sure we respect this required project structure (see enclosed)
>
> keep any additional files that are needed for the frontend backend or agents to actually run, but don't remove or relocate any of the required files above
>
> include both database files in the public repo
> -"data/campus_customs.db"
> -"data/campus_customs_new.db"
>
> do not include our real ".env" or any real API keys
>
> include ".env.example" with placeholders only
>
> make sure "README.md" explains
> -how to copy/reset the original database into the working database for a clean run
> -how to start the MCP server
> -how to start the FastAPI backend
> -how to start the React board
> -how to reset the database before a full 3-ticket run
>
> before pushing check
> -all required files and folders are in the right locations
> -the project can still run with this structure
> -no real secrets are included
> -both databases are included
> -all propmts from Problem 1 to 11 are well registered in the file
>
> push the project to a public GitHub repository
>
> save the public repo URL in "output/github_url.txt"
>
> give us the same public GitHub URL so we can submit it on Canvas

Attached image (required project structure):

```
hw5/
├── AI_prompts.md
├── requirements.txt
├── .env.example
├── .gitignore
├── .mcp.json
├── README.md
├── data/
│   ├── campus_customs.db
│   └── campus_customs_new.db
├── mcp_server/
│   ├── server.py
│   └── README.md
├── frontend/
├── backend/
│   ├── main.py
│   ├── models.py
│   └── prompts/
│       ├── boss.md
│       ├── inventory.md
│       ├── accounting.md
│       ├── facilities.md
│       └── customer_service.md
└── output/
    ├── harness.md
    ├── mcp_smoke.json
    ├── desk_tickets.html
    ├── design.md
    ├── resolved_tickets.json
    ├── resolved_board.html
    ├── audit_trail.json
    └── github_url.txt
```

### Follow-up prompts

No follow-up prompt used.
