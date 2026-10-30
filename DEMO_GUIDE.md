# Saturday Demo Guide

## 1. Set up on your laptop (by Thursday)

Open a terminal in the `release-agent` folder.

**Windows**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Mac / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then:

```bash
python -m pytest -q          # should say: 72 passed
streamlit run app.py         # opens the app in your browser
```

**Groq key (for the "Ask the assistant" tab):** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste your key, or paste it into the sidebar box. The other three tabs work without any key and without internet.

The app checks which Groq models your key can use and picks the best one automatically; you can switch models in the sidebar. If a model isn't available to your key, it falls back to another one on its own.

## 2. Before you leave home on Saturday

- Start the app and click through both cycles once with **Next ▶**.
- Ask the assistant one question to check the Groq key works.
- Screenshots of the key screens are in `docs/screenshots/` as a backup if anything misbehaves.
- Keep the laptop charged and the app already running.

## 3. The demo (about 7 minutes)

**Opening (30 seconds)**
> "I've rebuilt our weekly and monthly release process as an AI assistant: the cutoffs, Acceptance, regression, approvals and the Production window. All the data is synthetic, for a made-up company. Nothing from any employer or client."

Say the last sentence early; it shows professional judgement.

### How the console reads ServiceNow

Each change ticket carries **CAB approved** (Yes/No), **Approved to P** (Yes/No), a **Status** (New → In progress → Deployed to A → Ready for release → Deployed to P → Closed), and two attachments: a **release note** and a **TR list**. Dependencies are not a separate field: like you do, the console reads them from the TR lists ("import after TR X of CR-Y").

> "Every Monday I take the change list from ServiceNow, open each release note and TR list, work out the dependencies, merge the TRs into one list, give it to Rev-Trac for the SAP transports, and later build a separate list of only the approved changes for Production. The console does all of that: it sends the TR lists to Rev-Trac and the CI/CD pipeline, and when they confirm the import, the ServiceNow Status is updated automatically and the change moves on the board."

### How deployment works

The console sends each TR list to the deployment tools: **SAP transports to Rev-Trac**, other packages to the **CI/CD pipeline**. Each TR comes back with a result; for SAP, the return code decides: RC 0 imported, RC 4 imported with warnings, RC 8 errors, RC 12+ cancelled. When every TR of a change is confirmed with RC 0 or 4, the **ServiceNow Status is set automatically** (Deployed to A / Deployed to P), recorded as "Rev-Trac integration". If a TR fails, the change stays In progress and is moved out. The connectors are **simulated** in this demo and built so the real Rev-Trac API can be plugged in later.

> If she asks: "The connector is a separate class with one method, submit a TR list and return per-TR results. Plugging in the real Rev-Trac API means rewriting that one class."

### Weekly release WR-2026-1010 (3 minutes)

The Release cycle tab opens on it. Click **Next ▶** through the stages:

| Stage | What to point out |
|---|---|
| Monday | **CR-2172** was carried over from last week and its Status is already **Deployed to A**, so it is *not* deployed to A again and is left out of the TR list; it still needs Approved to P by Friday. Five changes have CAB approved = Yes and Status = In progress at 15:00. On the right: the **consolidated TR list for A**, 8 TRs from 5 changes, ready to download for the deployment team. The TR list goes to the **CI/CD pipeline**; when it confirms each import, the Status is set to **Deployed to A** automatically and the change moves into that column. Scroll down on the right to see the job and the result per TR. |
| Tuesday | **CR-2158** is In progress but **CAB approved = No**. **CR-2161** has **no release note or TR list attached**. **CR-2031**'s A deployment fails, so its Status stays In progress. All three move to next week. |
| Wednesday | **CR-2033** went In progress after Tuesday's cutoff, so it rolled into Wednesday. **CR-2036** is an emergency fix. **CR-2156** is still **Status New**. **CR-2042** needs downtime, and **CR-2043**'s TR list must be imported after CR-2042's TR: neither is allowed in a weekly release, so both are redirected to the November monthly. |
| Thursday | **CR-2052** went In progress at 15:40, after the final cutoff, so it moves to next week. |
| Friday | No A deployments. **CR-2045** fails regression. **CR-2048** has **Approved to P = No**: *"Not approved by user"*. **CR-2164**'s user set Approved to P = Yes, but the Status was never moved to **Ready for release**, so it's out too. On the right: the **segregated TR list for P**, 14 TRs from the 9 approved changes, with a separate **do not deploy** list for the TRs already on A that must not go to Production. |
| Saturday | The segregated TR list goes to the deployment tools; each confirmed import sets the Status to **Deployed to P** automatically, 9 changes between 08:00 and 10:00. |
| Close | Deployed changes are Closed. Closure report with every moved-out change, its reason, the rule and where it went. |

**Click any CR number** (in the event feed, on the board, in the TR lists, the cutover plan or the closure report) and its change record opens in a new tab, **as of the stage you clicked from**. At the top: the ticket's **attachments**, a **Word release note** (`Release_Note_CR-xxxx.docx`) and an **Excel TR list** (`TR_List_CR-xxxx.xlsx`). Click either to open it, just like opening an attachment in ServiceNow. A preview of both is shown underneath, with "import after" links to the change it depends on. Then Status, CAB approved and Approved to P at that moment, the release gates, the status history (who changed what and when, including the deployment team), related changes, commits, incidents and the activity log.

Good ones to click: **CR-2018** on Friday (Ready for release) and again on Saturday (Deployed to P), and **CR-2048** on Friday (Approved to P = No, Production gate "Not met").

### Monthly release MR-2026-10 (3 minutes)

Switch **Cycle** to **Monthly** and click **Next ▶**:

| Stage | What to point out |
|---|---|
| D1 (Tue 6 Oct) | Every change needs CAB approved = Yes and Status = In progress by D1. **CR-2159** has CAB approved = No, and **CR-2088** only went In progress on Wednesday morning: both move to November. |
| Extraction (Wed 7 Oct) | Scope frozen; the dependencies are read from the TR lists. The system cleaning activity **CR-2061** takes 5.5 hours on the HANA database, so the HANA patch **CR-2064** doesn't fit the 6-hour window and moves to November. |
| A deployment (Mon 12 Oct) | The **consolidated TR list for A**: 24 TRs from 15 changes, in dependency order (CR-2056's SAP TRs before CR-2057's). It goes to **Rev-Trac** (9 SAP transports) and the **CI/CD pipeline** (15 packages); the table on the right shows the return code per TR. **CR-2168**'s SAP transport fails in Rev-Trac with **RC 8** (object locked), so its other TRs are skipped, its Status stays In progress and it moves to November. **CR-2073** fails in the pipeline. Everything else is set to Deployed to A automatically. |
| Regression week 1 | The SAP transport **CR-2057** fails regression, and **CR-2059**, whose TR must follow it, is pulled automatically. Open CR-2057 to show the TR list and the "import after" link. |
| Go/No-Go (Sat 24 Oct) | The Oracle patch **CR-2068** has Approved to P = No: *"Not approved by user"*, so its dependent **CR-2070** goes too. **CR-2092** never sent downtime comms. On the right: the **segregated TR list for P** (11 TRs from 8 changes) and the **do not deploy** list. |
| P cutover (Sun 00:00–06:00) | The cutover plan: one change at a time per system; the CRM change **CR-2082** waits for the Kafka upgrade **CR-2080**; everything finishes by 05:30. |

> "This is the part that normally takes hours before every monthly: who's out, what that takes out with it, the TR list for the deployment team, and whether the cutover fits the window."

### Release calendar tab (30 seconds)
October at a glance: the daily weekly intake, D1, extraction, A deployment, the purple regression weeks, Go/No-Go and both Production windows, plus the freezes.

### Change explorer tab (30 seconds)
**CR-2056** (the SAP support package) is pre-selected: the dependency chain and "if this change is delayed, CR-2057 and CR-2059 are blocked."

### Ask the assistant (1 minute)
Click **"Why was CR-2048 moved out?"**, then **"What is the cutover plan for the monthly release?"**
> "The AI doesn't decide anything. The release rules decide; the AI explains the result and cites the policy rule, so it can't talk a change into Production."

### Close (30 seconds)
> "Next I'm splitting it into specialist agents with Google ADK and deploying it on GCP. I'm moving back to Bangalore in December and looking for GenAI or LLMOps roles, where release management experience is a real advantage. Would you be comfortable referring me, or introducing me to someone who's hiring?"

## 4. Questions she might ask

**"Is this real company data?"** No. A generator script creates it for a fictional company. The demo week and month are scripted, so the story is the same every time, and the other releases are randomised.

**"How do you know it's right?"** 72 automated tests: every scripted scenario must end with the expected outcome and rule, dependencies must come only from the TR lists, the A TR list must contain exactly the scoped changes' TRs in dependency order, the P TR list only the approved ones, the other releases must deploy cleanly, the weekly release must never deploy downtime or dependent changes, and every cutover plan must respect dependencies and the window.

**"Could it work with real ServiceNow?"** Yes. The data follows ServiceNow change-request fields, so only the data loader would switch to the ServiceNow Table API.

**"What does the AI actually do?"** It gets the engine's stage-by-stage results, the relevant change records and the policy text, and writes the explanation, citing change IDs and rule IDs.

## 5. Bring

- Your resume as a PDF on your phone, plus one printed copy
- One line she can forward: *"10 years in release and configuration management, now building GenAI and agentic AI systems; looking for GenAI engineer or LLMOps roles in Bangalore from January 2027."*
