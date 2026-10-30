"""
AI-Driven Change and Release Management Assistant - demo UI.

Run:  streamlit run app.py
"""

import calendar as pycal
import html
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from release_assistant.assistant import DEFAULT_MODEL, answer, available_models
from release_assistant.cycles import (APPROVED, BOARD_COLUMNS, DEPLOYED, IN_A, MOVED,
                                      ReleaseCycle, delay_impact, upstream_chain)
from release_assistant.data import load, parse
from record_page import cr_link, render_record

st.set_page_config(page_title="Release Management Assistant", layout="wide")

CSS = """
<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}
.hero {background:#1F2A44; color:#fff; border-radius:14px; padding:18px 24px; margin-bottom:14px;}
.hero h1 {color:#fff; font-size:26px; margin:0 0 4px 0; font-weight:600;}
.hero p {color:#C9D1E6; margin:0; font-size:14px;}
.pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px;
       font-weight:600; margin-right:6px;}
.pill.weekly {background:#E7F5FF; color:#1864AB;} .pill.monthly {background:#F3F0FF; color:#5F3DC4;}
.stepper {display:flex; align-items:flex-start; margin:10px 0 18px 0;}
.step {flex:1; text-align:center; position:relative; font-size:12px; color:#868E96;}
.step:before {content:""; position:absolute; top:13px; left:-50%; width:100%; height:3px;
              background:#DEE2E6; z-index:0;}
.step:first-child:before {display:none;}
.step.done:before, .step.current:before {background:#3B5BDB;}
.dot {width:28px; height:28px; border-radius:50%; background:#DEE2E6; color:#495057;
      display:flex; align-items:center; justify-content:center; margin:0 auto 6px auto;
      position:relative; z-index:1; font-weight:600; font-size:12px;}
.step.done .dot {background:#3B5BDB; color:#fff;}
.step.current .dot {background:#fff; color:#3B5BDB; box-shadow:0 0 0 3px #3B5BDB;}
.step.current {color:#1F2430; font-weight:600;} .step.done {color:#495057;}
.stage {background:#fff; border:1px solid #E9ECEF; border-radius:12px; padding:14px 18px;
        margin-bottom:12px;}
.stage h3 {margin:0; font-size:20px;} .stage .when {color:#495057; font-size:14px;}
.ev {background:#fff; border:1px solid #E9ECEF; border-left:4px solid #ADB5BD;
     border-radius:8px; padding:8px 12px; margin-bottom:6px; font-size:14px;}
.ev.ok {border-left-color:#2F9E44;} .ev.moved {border-left-color:#E03131; background:#FFF5F5;}
.ev.warn {border-left-color:#F08C00;} .ev.info {border-left-color:#ADB5BD;}
.cr {font-family:ui-monospace,Menlo,Consolas,monospace; font-weight:700; color:#364FC7;
     margin-right:6px; text-decoration:none;}
a.cr:hover {text-decoration:underline;}
.card a.cr {display:block;}
.rule {font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; background:#F1F3F5;
       color:#495057; padding:1px 6px; border-radius:5px; margin-left:6px; white-space:nowrap;}
.board {display:grid; gap:10px;}
.col {background:#EEF0F3; border-radius:10px; padding:8px; min-height:80px;}
.col h4 {font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:#495057;
         margin:2px 4px 6px 4px;}
.col h4 span {color:#868E96; font-weight:400;}
.card {background:#fff; border:1px solid #E3E6EA; border-radius:8px; padding:6px 8px;
       margin-bottom:6px; font-size:12px; line-height:1.35;}
.card .app {color:#495057;} .card .desc {color:#868E96;}
.card.moved {border-left:3px solid #E03131;} .card.done {border-left:3px solid #2F9E44;}
.card .to {color:#C92A2A; font-weight:600;}
.gantt-axis {display:flex; margin-left:300px; font-size:11px; color:#868E96;}
.gantt-axis div {flex:1; border-left:1px solid #DEE2E6; padding-left:3px;}
.grow {display:flex; align-items:center; margin:4px 0;}
.glabel {width:300px; font-size:12px; padding-right:8px; white-space:nowrap; overflow:hidden;
         text-overflow:ellipsis;}
.gtrack {flex:1; position:relative; height:24px; background:#F1F3F5; border-radius:6px;}
.gbar {position:absolute; top:3px; height:18px; border-radius:5px; background:#4C6EF5;
       color:#fff; font-size:11px; padding:1px 6px; white-space:nowrap; overflow:hidden;}
.gbar.down {background:#7048E8;}
.cal {display:grid; grid-template-columns:repeat(7,1fr); gap:6px;}
.cal .hd {font-size:12px; color:#868E96; text-align:center; font-weight:600;}
.cal .day {background:#fff; border:1px solid #E9ECEF; border-radius:8px; min-height:92px;
           padding:4px 6px; font-size:11px;}
.cal .day.reg {background:#F8F4FF;} .cal .day.empty {background:transparent; border:none;}
.cal .num {font-weight:600; color:#495057; font-size:12px;}
.tag {display:block; border-radius:5px; padding:1px 5px; margin-top:3px; font-weight:600;}
.tag.w {background:#E7F5FF; color:#1864AB;} .tag.wp {background:#1C7ED6; color:#fff;}
.tag.m {background:#F3F0FF; color:#5F3DC4;} .tag.mp {background:#7048E8; color:#fff;}
.tag.fz {background:#FFF4E6; color:#D9480F;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

STATUS_ORDER = BOARD_COLUMNS
WEEKLY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat P", "Close"]
MONTHLY_SHORT = ["D1", "Extract", "A deploy", "Reg wk 1", "Reg wk 2", "Go/No-Go",
                 "P cutover", "Close"]
EXAMPLES = [
    "Summarize this week's weekly release for CAB.",
    "Why was CR-2048 moved out?",
    "What is the cutover plan for the monthly release?",
    "What happens if CR-2056 is delayed?",
]


@st.cache_resource
def get_data():
    return load()


@st.cache_resource
def get_cycle(release_id):
    return ReleaseCycle(get_data(), release_id)


def esc(s):
    return html.escape(str(s))


@st.cache_data(ttl=3600, show_spinner=False)
def list_models(api_key):
    return available_models(api_key)


def api_key_from_env():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        try:
            key = st.secrets.get("GROQ_API_KEY")
        except Exception:
            key = None
    return key


data = get_data()

# A CR link opens the change record in its own tab: ?cr=CR-xxxx
_cr = st.query_params.get("cr")
if _cr and _cr in data.by_id:
    render_record(data, get_cycle(data.by_id[_cr]["requested_release"]), _cr,
                  st.query_params.get("step"))
    st.stop()

with st.sidebar:
    st.subheader("About this demo")
    st.caption("AI-Driven Change & Release Management Assistant. All data is synthetic, "
               "for a fictional company (Orbitra Retail). No real company or client data.")
    st.caption("Decisions come from deterministic release rules; the AI explains them "
               "and cites the policy.")
    st.divider()
    api_key = api_key_from_env() or st.text_input("Groq API key (Ask tab)", type="password")
    model = None
    if api_key:
        try:
            models = list_models(api_key)
        except Exception as e:  # show the problem instead of failing silently
            models = []
            st.caption(f"Could not list Groq models: {e}")
        if models:
            model = st.selectbox("Model", models, help="Models your Groq key can use.")

st.markdown("""<div class="hero"><h1>AI Change &amp; Release Management Assistant</h1>
<p>Weekly and monthly release cycles, end to end: cutoffs, Acceptance, regression,
approvals, Production and closure, with every decision traced to a policy rule.</p></div>""",
            unsafe_allow_html=True)

tab_cycle, tab_cal, tab_change, tab_ask = st.tabs(
    ["Release cycle", "Release calendar", "Change explorer", "Ask the assistant"])


# ============================================================ release cycle
def render_stepper(cycle, idx):
    short = WEEKLY_SHORT if cycle.cal["type"] == "Weekly" else MONTHLY_SHORT
    parts = []
    for i, label in enumerate(short):
        cls = "done" if i < idx else "current" if i == idx else ""
        mark = "✓" if i < idx else str(i + 1)
        parts.append(f'<div class="step {cls}"><div class="dot">{mark}</div>{esc(label)}</div>')
    st.markdown(f'<div class="stepper">{"".join(parts)}</div>', unsafe_allow_html=True)


def render_events(events, step=None):
    out = []
    for e in events:
        cr = cr_link(e["change_id"], step=step) if e["change_id"] else ""
        app = ""
        if e["change_id"]:
            app = f'<span style="color:#868E96">{esc(data.by_id[e["change_id"]]["application"])}'\
                  ' · </span>'
        rule = f'<span class="rule">{esc(e["rule"])}</span>' if e["rule"] else ""
        out.append(f'<div class="ev {e["kind"]}">{cr}{app}{esc(e["text"])}{rule}</div>')
    st.markdown("".join(out), unsafe_allow_html=True)


def render_board(cycle, board, step=None):
    used = [s for s in STATUS_ORDER if any(s in st_["board"].values() for st_ in cycle.steps)]
    cols = []
    for s in used:
        ids = [cid for cid, v in board.items() if v == s]
        cards = []
        for cid in sorted(ids):
            c = data.by_id[cid]
            cls = "moved" if s == MOVED else "done" if s == DEPLOYED else ""
            extra = ""
            if s == MOVED and cid in cycle.moved:
                m = cycle.moved[cid]
                extra = (f'<div class="to" title="{esc(m["reason"])}">→ {esc(m["target"])} · '
                         f'{esc(m["rule"])}</div>')
            desc = c["short_description"]
            desc = desc if len(desc) < 44 else desc[:42] + "…"
            cards.append(f'<div class="card {cls}">{cr_link(cid, step=step)}'
                         f'<div class="app">{esc(c["application"])}</div>'
                         f'<div class="desc">{esc(desc)}</div>{extra}</div>')
        cols.append(f'<div class="col"><h4>{esc(s)} <span>{len(ids)}</span></h4>'
                    f'{"".join(cards)}</div>')
    st.markdown(f'<div class="board" style="grid-template-columns:repeat({len(used)},1fr)">'
                f'{"".join(cols)}</div>', unsafe_allow_html=True)


def render_gantt(cycle, step=None):
    start, end = cycle.cal["p_start"], cycle.cal["p_end"]
    total = (end - start).total_seconds() / 60
    step = 30 if total <= 120 else 60
    ticks = [start + timedelta(minutes=m) for m in range(0, int(total), step)]
    rows = ['<div class="gantt-axis">' +
            "".join(f"<div>{t:%H:%M}</div>" for t in ticks) + "</div>"]
    for p in sorted(cycle.deploy_plan, key=lambda p: (p["start"], p["system"])):
        c = data.by_id[p["change_id"]]
        left = (p["start"] - start).total_seconds() / 60 / total * 100
        width = max((p["end"] - p["start"]).total_seconds() / 60 / total * 100, 3)
        down = " down" if c["downtime_required"] else ""
        after = f" after {', '.join(p['depends_on'])}" if p["depends_on"] else ""
        rows.append(
            f'<div class="grow"><div class="glabel">{cr_link(p["change_id"], step=step)} '
            f'{esc(c["application"])} <span style="color:#868E96">· {esc(p["system"])}</span></div><div class="gtrack"><div class="gbar{down}" '
            f'style="left:{left:.1f}%;width:{width:.1f}%" title="{esc(c["short_description"])}">'
            f'{p["start"]:%H:%M}–{p["end"]:%H:%M}{esc(after)}</div></div></div>')
    st.markdown("".join(rows), unsafe_allow_html=True)
    st.caption("Purple = change with downtime. One change at a time per system; dependent "
               "changes start after the change they depend on.")


def render_jobs(jobs, idx):
    """Deployment tool jobs and their per-TR confirmations (simulated connectors)."""
    for j in jobs:
        failed = sum(r["Result"] == "Failed" for r in j["results"])
        badge = f":red[**{failed} failed**]" if failed else ":green[**all imported**]"
        st.markdown(f"**{j['tool']}** · job `{j['job_id']}` · {len(j['results'])} TR(s) · "
                    f"finished {j['finished_at']:%H:%M} · {badge}")
        df = pd.DataFrame([{
            "TR": r["TR"], "Change": f"?cr={r['Change']}&step={idx}",
            "RC": "—" if r["RC"] is None else str(r["RC"]), "Result": r["Result"],
            "Finished": r["Finished"].strftime("%H:%M") if r["Finished"] else "",
            "Message": r["Message"]} for r in j["results"]])
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Change": st.column_config.LinkColumn("Change", display_text=r"\?cr=([^&]*)")})
    st.caption("Rev-Trac takes the SAP transports, the CI/CD pipeline the other packages. "
               "When a tool confirms every TR of a change (RC 0 or 4), the ServiceNow Status "
               "is updated automatically. Connectors are simulated for this demo.")


def render_handover(h, idx, release_id):
    """The TR list the release manager hands to the deployment team."""
    env = h["env"]
    st.markdown(f"#### {h['title']}")
    st.caption(("Merged from the TR lists of all changes taken into A today, in dependency "
                "order." if env == "A" else
                "Only changes with Approved to P = Yes and Status Ready for release, in "
                "dependency order. Excluded TRs are listed separately as do-not-deploy.")
               + " Click a change to open its release note and TR list.")
    if not h["rows"]:
        st.info("No TRs to hand over.")
        return
    df = pd.DataFrame(h["rows"])
    view = df.assign(Change="?cr=" + df["Change"] + f"&step={idx}")
    st.dataframe(view, hide_index=True, width="stretch",
                 column_order=["Seq", "TR", "Change", "Type", "Target", "Import after"],
                 column_config={
                     "Change": st.column_config.LinkColumn("Change",
                                                           display_text=r"\?cr=([^&]*)"),
                     "Seq": st.column_config.NumberColumn("Seq", width="small")})
    st.caption("The CSV download also includes application and TR descriptions.")
    fname = f"{release_id}_TR_list_{env}_{h['when']:%Y%m%d}.csv"
    csv = df.to_csv(index=False)
    if h["excluded"]:
        st.markdown(f"**Do not deploy** ({len(h['excluded'])} TRs)")
        ex = pd.DataFrame(h["excluded"])
        st.dataframe(ex.assign(Change="?cr=" + ex["Change"] + f"&step={idx}"),
                     hide_index=True, width="stretch",
                     column_order=["TR", "Change", "Reason"], column_config={
                         "Change": st.column_config.LinkColumn(
                             "Change", display_text=r"\?cr=([^&]*)")})
        csv += "\nDO NOT DEPLOY\n" + ex.to_csv(index=False)
    st.download_button(f"Download TR list for {env} (CSV)", csv, file_name=fname,
                       mime="text/csv", key=f"dl_{release_id}_{idx}")
    jobs = cycle.jobs.get(step["key"]) if env == "A" else None
    if jobs:
        st.markdown("#### Deployment tool confirmations")
        render_jobs(jobs, idx)


with tab_cycle:
    releases = data.releases
    c1, c2 = st.columns([1, 3])
    kind = c1.radio("Cycle", ["Weekly", "Monthly"], horizontal=True)
    options = [r for r in releases if r["type"] == kind]
    demo_id = "WR-2026-1010" if kind == "Weekly" else "MR-2026-10"
    idx0 = next(i for i, r in enumerate(options) if r["release_id"] == demo_id)
    rel = c2.selectbox("Release", options, index=idx0,
                       format_func=lambda r: f"{r['release_id']} · {r['name']}")
    cycle = get_cycle(rel["release_id"])
    key = f"step_{rel['release_id']}"
    st.session_state.setdefault(key, 0)
    last = len(cycle.steps) - 1

    b1, b2, b3, b4, _ = st.columns([1, 1, 1, 1, 4])
    if b1.button("◀ Previous", width="stretch", disabled=st.session_state[key] == 0):
        st.session_state[key] -= 1
    if b2.button("Next ▶", type="primary", width="stretch",
                 disabled=st.session_state[key] == last):
        st.session_state[key] += 1
    if b3.button("Run to end", width="stretch"):
        st.session_state[key] = last
    if b4.button("Restart", width="stretch"):
        st.session_state[key] = 0
    idx = st.session_state[key]
    step = cycle.steps[idx]

    render_stepper(cycle, idx)
    pill = f'<span class="pill {kind.lower()}">{kind}</span>'
    st.markdown(f'<div class="stage">{pill}<span class="rule">{rel["release_id"]}</span>'
                f'<h3>{esc(step["title"])}</h3><div class="when">'
                f'{step["when"]:%A %d %B %Y, %H:%M} IST · {esc(step["subtitle"])}</div></div>',
                unsafe_allow_html=True)

    board = step["board"]
    k = st.columns(5)
    k[0].metric("Requested", len(board))
    k[1].metric("Deployed to A", sum(v == IN_A for v in board.values()))
    k[2].metric("Ready for release", sum(v == APPROVED for v in board.values()))
    k[3].metric("Deployed to P", sum(v == DEPLOYED for v in board.values()))
    k[4].metric("Moved out", sum(v == MOVED for v in board.values()))

    if step["key"] == "production":
        st.markdown("#### Production deployment plan")
        render_gantt(cycle, idx)
    left, right = st.columns([2, 3])
    with left:
        st.markdown("#### What happened")
        render_events(step["events"], idx)
    with right:
        if step["key"] == "production":
            st.markdown("#### Deployment summary")
            deployed = [p for p in cycle.deploy_plan]
            end = max(p["end"] for p in deployed) if deployed else None
            st.markdown(f"- **{len(deployed)} changes** deployed across "
                        f"**{len({p['system'] for p in deployed})} systems**")
            if end:
                st.markdown(f"- Window {cycle.cal['p_start']:%H:%M}–{cycle.cal['p_end']:%H:%M}"
                            f", last change finished at **{end:%H:%M}**")
            down = sum(data.by_id[p['change_id']]['downtime_required'] for p in deployed)
            st.markdown(f"- {down} with downtime, "
                        f"{sum(bool(p['depends_on']) for p in deployed)} sequenced after a "
                        "dependency")
            if cycle.jobs.get("production"):
                st.markdown("#### Deployment tool confirmations")
                render_jobs(cycle.jobs["production"], idx)
        elif step["key"] == "closure":
            st.markdown("#### Release closure report")
            rows = [{"Change": cid, "Application": data.by_id[cid]["application"],
                     "Outcome": "Deployed to P" if s == DEPLOYED else "Moved out",
                     "Stage": cycle.moved.get(cid, {}).get("stage", ""),
                     "Reason": cycle.moved.get(cid, {}).get("reason", ""),
                     "Rule": cycle.moved.get(cid, {}).get("rule", ""),
                     "Moved to": cycle.moved.get(cid, {}).get("target", "")}
                    for cid, s in board.items()]
            df = pd.DataFrame(rows).sort_values(["Outcome", "Change"])
            view = df.assign(Change="?cr=" + df["Change"] + f"&step={idx}")
            st.dataframe(view, hide_index=True, width="stretch", column_config={
                "Change": st.column_config.LinkColumn("Change", display_text=r"\?cr=([^&]*)")})
            st.download_button("Download closure report (CSV)", df.to_csv(index=False),
                               file_name=f"{rel['release_id']}_closure.csv", mime="text/csv")
        else:
            h = cycle.handovers.get(step["key"])
            if h:
                render_handover(h, idx, rel["release_id"])
            st.markdown("#### Policy rules applied at this stage")
            rules = sorted({e["rule"] for e in step["events"] if e["rule"]})
            for r in rules:
                p = data.policies.get(r)
                if p:
                    with st.expander(f"{r} · {p['title']}"):
                        st.markdown(p["text"])
                        st.caption(p["source"])
            if not rules:
                st.caption("No rules triggered at this stage.")
    st.markdown("#### Release board")
    render_board(cycle, board, idx)


# ========================================================= release calendar
with tab_cal:
    month = st.radio("Month", ["October 2026", "November 2026"], horizontal=True)
    y, m = (2026, 10) if month.startswith("Oct") else (2026, 11)
    tags = {}

    def tag(d, cls, text):
        tags.setdefault(d, []).append(f'<span class="tag {cls}">{esc(text)}</span>')

    reg_days = set()
    for r in data.releases:
        if r["type"] == "Weekly":
            tag(parse(r["p_start"]).date(), "wp", f"{r['release_id']} P 08–10")
            for d in r["intake_days"]:
                tag(date.fromisoformat(d), "w", "WR intake · A 16:00")
            tag(date.fromisoformat(r["regression_day"]), "w", "WR regression + approvals")
        else:
            rid = r["release_id"]
            tag(parse(r["d1"]).date(), "m", f"{rid} D1")
            tag(parse(r["extraction"]).date(), "m", f"{rid} extraction")
            tag(parse(r["a_deploy"]).date(), "m", f"{rid} A deployment")
            tag(parse(r["go_no_go"]).date(), "m", f"{rid} Go/No-Go")
            tag(parse(r["p_start"]).date(), "mp", f"{rid} P 00–06")
            d = parse(r["regression_start"]).date()
            while d < parse(r["go_no_go"]).date():
                reg_days.add(d)
                d += timedelta(days=1)
    for z in data.freezes:
        d = parse(z["start"]).date()
        while d <= parse(z["end"]).date():
            if d.month == m:
                tag(d, "fz", f"Freeze: {z['name']}")
            d += timedelta(days=1)

    cells = [f'<div class="hd">{n}</div>' for n in ["Mon", "Tue", "Wed", "Thu", "Fri",
                                                     "Sat", "Sun"]]
    first = date(y, m, 1)
    cells += ['<div class="day empty"></div>'] * first.weekday()
    for day in range(1, pycal.monthrange(y, m)[1] + 1):
        d = date(y, m, day)
        cls = "day reg" if d in reg_days else "day"
        cells.append(f'<div class="{cls}"><div class="num">{day}</div>'
                     f'{"".join(tags.get(d, []))}</div>')
    st.markdown(f'<div class="cal">{"".join(cells)}</div>', unsafe_allow_html=True)
    st.caption("Light purple days = monthly regression testing on Acceptance.")

    st.markdown("#### Releases")
    st.dataframe(pd.DataFrame([{
        "Release": r["release_id"], "Type": r["type"], "Name": r["name"],
        "Production": parse(r["p_start"]).strftime("%a %d %b %H:%M") + "–" +
        parse(r["p_end"]).strftime("%H:%M"),
        "Release manager": r["release_manager"],
        "Requested": len(r["change_ids"]),
        "Deployed": len(get_cycle(r["release_id"]).summary()["deployed"]),
        "Moved out": len(get_cycle(r["release_id"]).moved),
    } for r in data.releases]), hide_index=True, width="stretch")


# ========================================================== change explorer
with tab_change:
    ids = [c["change_id"] for c in data.changes]
    default = ids.index("CR-2056") if "CR-2056" in ids else 0
    cid = st.selectbox("Change", ids, index=default,
                       format_func=lambda x: f"{x} · {data.by_id[x]['application']} · "
                                             f"{data.by_id[x]['short_description']}")
    c = data.by_id[cid]
    cy = get_cycle(c["requested_release"])
    outcome = cy.status[cid]
    a, b = st.columns([3, 2])
    with a:
        chips = [c["requested_release"], c["work_type"], c["change_type"], f"Risk {c['risk']}",
                 f"Priority {c['priority']}", c["system"],
                 f"Downtime {c['downtime_minutes']} min" if c["downtime_required"]
                 else "No downtime"]
        st.markdown("".join(f'<span class="rule">{esc(x)}</span>' for x in chips),
                    unsafe_allow_html=True)
        st.markdown(f"### {c['short_description']}")
        st.markdown(f'<a href="?cr={cid}" target="_blank">Open change record ↗</a>',
                    unsafe_allow_html=True)
        if outcome == MOVED:
            m_ = cy.moved[cid]
            st.error(f"**Moved out at {m_['stage']}**: {m_['reason']} → {m_['target']} "
                     f"(`{m_['rule']}`)")
        else:
            plan = next((p for p in cy.deploy_plan if p["change_id"] == cid), None)
            when = f" {plan['start']:%a %d %b %H:%M}–{plan['end']:%H:%M}" if plan else ""
            st.success(f"**Deployed to Production**{when}")
        st.markdown(f"In progress since: **{parse(c['submitted_at']):%a %d %b %H:%M}** · "
                    f"CAB approved: **{c['cab_approved']}** · Approved to P: "
                    f"**{c['approved_to_p']}** · TRs: **{len(c['tr_list'])}** · "
                    f"Assigned to {c['assignment_group']}")
    with b:
        chain = upstream_chain(data, cid)
        impact = delay_impact(data, cid)
        nodes = set([cid] + chain + [i["change_id"] for i in impact])
        if len(nodes) > 1:
            dot = ['digraph G {rankdir=TB; node [shape=box, style="rounded,filled", '
                   'fontname="Helvetica", fontsize=14, color="#ADB5BD", margin="0.25,0.12"];']
            for n in nodes:
                nc = data.by_id[n]
                moved = get_cycle(nc["requested_release"]).status[n] == MOVED
                fill = "#FFE3E3" if moved else "#D3F9D8"
                pen = ", penwidth=2.5" if n == cid else ""
                dot.append(f'"{n}" [label="{n}\\n{nc["application"]}", fillcolor="{fill}"{pen}];')
            for n in nodes:
                for d in data.by_id[n]["depends_on"]:
                    if d in nodes:
                        dot.append(f'"{d}" -> "{n}";')
            st.graphviz_chart("\n".join(dot) + "}")
            st.caption("Arrows point to dependent changes. Green = deployed, red = moved out.")
            if impact:
                st.markdown("**If this change is delayed:** " + ", ".join(
                    f"{i['change_id']} ({i['application']})" for i in impact) + " are blocked.")
        else:
            st.caption("No dependencies.")
    with st.expander("Source record (ServiceNow fields)"):
        st.json(c, expanded=False)


# ======================================================== ask the assistant
with tab_ask:
    st.caption(f"Answers are grounded in the release engine's results and the policy "
               f"documents (model: {model or DEFAULT_MODEL}).")
    st.session_state.setdefault("chat", [])
    cols = st.columns(len(EXAMPLES))
    clicked = None
    for col, ex in zip(cols, EXAMPLES):
        if col.button(ex, width="stretch"):
            clicked = ex
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                st.caption("Sources: " + ", ".join(msg["sources"]))
    question = st.chat_input("Ask about releases, changes, approvals, dependencies…") or clicked
    if question:
        if not api_key:
            reply, sources = ("Add a Groq API key in the sidebar to use the assistant. "
                              "The other tabs work without one."), []
        else:
            with st.spinner("Checking the release data…"):
                try:
                    history = [{"role": x["role"], "content": x["content"]}
                               for x in st.session_state.chat]
                    reply, sources, used = answer(question, data, api_key, model=model,
                                                  history=history)
                    if model and used != model:
                        sources = sources + [f"model {used}"]
                except Exception as e:  # show the problem instead of failing silently
                    reply, sources = (f"The AI call failed: `{e}`. The other tabs still "
                                      "work."), []
        st.session_state.chat += [{"role": "user", "content": question},
                                  {"role": "assistant", "content": reply, "sources": sources}]
        st.rerun()
