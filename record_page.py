"""
Change record page: what you would see when opening a change request in the
ITSM tool. Opened from any CR link in the app (?cr=CR-xxxx), in a new tab.

This is a mock record built from synthetic data. It is not connected to, and
does not imitate the branding of, any real ITSM product.
"""

import html
from datetime import datetime

import streamlit as st

from release_assistant.cycles import DEPLOYED, MOVED, dependents, status_at
from release_assistant.data import DATA_DIR, parse

RECORD_CSS = """
<style>
.rec-top {background:#1F2A44; color:#fff; border-radius:12px 12px 0 0; padding:14px 22px;
          display:flex; justify-content:space-between; align-items:center;}
.rec-top .num {font-family:ui-monospace,Menlo,Consolas,monospace; font-size:22px;
               font-weight:700;}
.rec-top .kind {color:#C9D1E6; font-size:13px;}
.rec-state {padding:4px 12px; border-radius:999px; font-size:13px; font-weight:700;}
.rec-state.ok {background:#D3F9D8; color:#1B5E20;} .rec-state.info {background:#DBE4FF; color:#2F44A8;}
.asof {background:#FFF9DB; border:1px solid #FFE066; border-radius:8px; padding:8px 14px; font-size:14px; margin-bottom:10px;} .rec-state.moved {background:#FFE3E3; color:#A61E1E;}
.rec-body {background:#fff; border:1px solid #E3E6EA; border-top:none; border-radius:0 0 12px 12px;
           padding:18px 22px; margin-bottom:16px;}
.rec-grid {display:grid; grid-template-columns:1fr 1fr; column-gap:36px;}
.rec-row {display:flex; border-bottom:1px solid #F1F3F5; padding:7px 0; font-size:14px;}
.rec-row .k {width:190px; color:#6B7280; flex-shrink:0;} .rec-row .v {color:#1F2430;}
.rec-sec {background:#fff; border:1px solid #E3E6EA; border-radius:12px; padding:14px 22px;
          margin-bottom:16px;}
.rec-sec h4 {margin:0 0 10px 0; font-size:15px; text-transform:uppercase; letter-spacing:.04em;
             color:#495057;}
.rec-desc {font-size:14px; line-height:1.55; color:#1F2430;}
.rec-tbl {width:100%; border-collapse:collapse; font-size:14px;}
.rec-tbl th {text-align:left; color:#6B7280; font-weight:600; border-bottom:1px solid #E3E6EA;
             padding:6px 8px;}
.rec-tbl td {border-bottom:1px solid #F1F3F5; padding:7px 8px;}
.ok-txt {color:#2B8A3E; font-weight:600;} .bad-txt {color:#C92A2A; font-weight:600;}
.act {border-left:3px solid #DEE2E6; margin-left:6px; padding:0 0 0 16px;}
.act-item {position:relative; padding:0 0 14px 0; font-size:14px;}
.act-item:before {content:""; position:absolute; left:-23px; top:4px; width:11px; height:11px;
                  border-radius:50%; background:#ADB5BD;}
.act-item.ok:before {background:#2F9E44;} .act-item.moved:before {background:#E03131;}
.act-item.info:before {background:#4C6EF5;}
.act-item .t {color:#6B7280; font-size:12px;}
.act-item .who {font-weight:600;}
.mono {font-family:ui-monospace,Menlo,Consolas,monospace;}
a.cr {text-decoration:none;} a.cr:hover {text-decoration:underline;}
</style>
"""


def esc(s):
    return html.escape(str(s))


def cr_link(cid, cls="cr", step=None):
    q = f"?cr={esc(cid)}" + (f"&step={step}" if step is not None else "")
    return f'<a class="{cls}" href="{q}" target="_blank">{esc(cid)}</a>'


def fmt(ts, pattern="%a %d %b %Y %H:%M"):
    if not ts:
        return "—"
    if isinstance(ts, str):
        ts = parse(ts)
    return ts.strftime(pattern)


def yes_no(flag, yes="Attached", no="Missing"):
    return f'<span class="ok-txt">{yes}</span>' if flag else f'<span class="bad-txt">{no}</span>'


def approval_cell(state):
    if state == "approved":
        return '<span class="ok-txt">Approved</span>'
    if state == "not_required":
        return "Not required"
    return f'<span class="bad-txt">{esc(state.capitalize())}</span>'


GOOD = ("Ready for release", "Deployed to A", "Deployed to P", "Closed")


def render_deployment_log(cycle, cid, upto):
    """Per-TR confirmations from Rev-Trac / the CI/CD pipeline, up to the viewed stage."""
    keys = [st_["key"] for st_ in cycle.steps[:upto + 1]]
    rows = ""
    for key in keys:
        for j in cycle.jobs.get(key, []):
            for r in j["results"]:
                if r["Change"] != cid:
                    continue
                cls = {"Failed": "bad-txt", "Skipped": ""}.get(r["Result"], "ok-txt")
                rows += (f'<tr><td>{esc(j["env"])}</td><td>{esc(j["tool"])}</td>'
                         f'<td class="mono">{esc(j["job_id"])}</td>'
                         f'<td class="mono">{esc(r["TR"])}</td>'
                         f'<td>{"" if r["RC"] is None else r["RC"]}</td>'
                         f'<td class="{cls}">{esc(r["Result"])}</td>'
                         f'<td>{fmt(r["Finished"]) if r["Finished"] else "—"}</td></tr>')
    if rows:
        st.markdown('<div class="rec-sec"><h4>Deployment log (Rev-Trac / CI/CD pipeline)</h4>'
                    '<table class="rec-tbl"><tr><th>Env</th><th>Tool</th><th>Job</th>'
                    '<th>TR</th><th>RC</th><th>Result</th><th>Finished</th></tr>'
                    f'{rows}</table></div>', unsafe_allow_html=True)


def render_attachments(data, c, step):
    """Release note (.docx) and TR list (.xlsx) attached to the ticket, openable like in
    ServiceNow, with a preview of their content below."""
    rn = c["release_note"]
    if not rn or not c.get("attachments"):
        st.markdown('<div class="rec-sec" style="border-color:#FFC9C9;background:#FFF5F5">'
                    '<h4 style="color:#C92A2A">Attachments</h4><div class="rec-desc">No release '
                    'note or TR list attached. The change cannot be taken into a release '
                    '(CHG-04).</div></div>', unsafe_allow_html=True)
        return
    st.markdown(f'<div class="rec-sec" style="margin-bottom:6px"><h4>Attachments '
                f'({len(c["attachments"])})</h4><div class="rec-desc">Files attached to the '
                f'ticket. Click to open them in Word or Excel.</div></div>',
                unsafe_allow_html=True)
    cols = st.columns(len(c["attachments"]) + 2)
    mimes = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml."
                      "document",
             ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    for col, a in zip(cols, c["attachments"]):
        path = DATA_DIR / a["path"]
        if not path.exists():
            col.warning(f"{a['name']} missing: run the data generator")
            continue
        icon = "📄" if a["name"].endswith(".docx") else "📊"
        col.download_button(f"{icon} {a['name']}", path.read_bytes(), file_name=a["name"],
                            mime=mimes.get(path.suffix, "application/octet-stream"),
                            key=f"att_{c['change_id']}_{a['name']}", width="stretch")

    steps = "".join(f"<li>{esc(x)}</li>" for x in rn["deployment_steps"])
    note = (f'<div class="rec-desc"><b>{esc(rn["title"])}</b><br>{esc(rn["summary"])}'
            f'<ol style="margin:8px 0 8px 18px;padding:0">{steps}</ol>'
            f'<b>Dependencies:</b> {esc(rn["dependencies"])}<br>'
            f'<b>Downtime:</b> {esc(rn["downtime"])}<br>'
            f'<b>Rollback:</b> {esc(rn["rollback"])}</div>')
    rows = ""
    for t in c["tr_list"]:
        after = ""
        if t["depends_on_tr"]:
            owner = data.tr_owner.get(t["depends_on_tr"])
            after = f'{esc(t["depends_on_tr"])} ({cr_link(owner, step=step) if owner else "?"})'
        rows += (f'<tr><td>{t["sequence"]}</td><td class="mono">{esc(t["tr_id"])}</td>'
                 f'<td>{esc(t["type"])}</td><td class="mono">{esc(t["a_target"])}</td>'
                 f'<td class="mono">{esc(t["p_target"])}</td><td>{after or "—"}</td></tr>')
    a, b = st.columns(2)
    a.markdown(f'<div class="rec-sec"><h4>Preview · Release note</h4>{note}</div>',
               unsafe_allow_html=True)
    b.markdown('<div class="rec-sec"><h4>Preview · TR list</h4><table class="rec-tbl">'
               '<tr><th>#</th><th>TR</th><th>Type</th><th>A target</th><th>P target</th>'
               f'<th>Import after</th></tr>{rows}</table></div>', unsafe_allow_html=True)


def happened(ts, as_of):
    return bool(ts) and parse(ts) <= as_of


def activity(data, cycle, c, upto, as_of):
    """Everything that happened to this change up to the stage being viewed."""
    cid = c["change_id"]
    items = []
    who_sets = {"Requester": c["requested_by"], "Change owner": c["assigned_to"]}
    for h in cycle.status_history(cid):
        if happened(h["at"], as_of):
            kind = "info" if h["status"] in ("New", "In progress") else "ok"
            items.append((parse(h["at"]), kind, who_sets.get(h["by"], h["by"]),
                          f"Status changed to <b>{esc(h['status'])}</b>"
                          + (f" for {esc(c['requested_release'])}"
                             if h["status"] == "In progress" else "")))
    if happened(c["approved_to_p_at"], as_of):
        items.append((parse(c["approved_to_p_at"]), "ok", "Business user",
                      "<b>Approved to P</b> set to Yes after testing on Acceptance"))
    if happened(c["cab_approved_at"], as_of):
        who = "ECAB" if c["change_type"] == "Emergency" else "CAB"
        items.append((parse(c["cab_approved_at"]), "ok", who,
                      "<b>CAB approved</b> set to Yes"))
    if happened(c["downtime_comms_sent_at"], as_of):
        items.append((parse(c["downtime_comms_sent_at"]), "info", "Release Management",
                      f"Downtime communication sent ({c['downtime_minutes']} min)"))
    for step in cycle.steps[:upto + 1]:
        if step["key"] == "closure":
            continue
        for e in step["events"]:
            if e["change_id"] == cid and "eployment team set Status" not in e["text"]:
                when = step["when"]
                if step["key"] == "production":
                    plan = next((p for p in cycle.deploy_plan if p["change_id"] == cid), None)
                    when = plan["start"] if plan else when
                rule = f' <span class="mono">[{esc(e["rule"])}]</span>' if e["rule"] else ""
                items.append((when, e["kind"], f"Release engine · {step['title']}",
                              esc(e["text"]) + rule))
    return sorted(items, key=lambda x: x[0])


def render_record(data, cycle, cid, step=None):
    """Show the change as it stood at cycle stage `step` (default: after closure)."""
    c = data.by_id[cid]
    st.markdown(RECORD_CSS, unsafe_allow_html=True)
    last = len(cycle.steps) - 1
    upto = last if step is None else max(0, min(int(step), last))
    stage = cycle.steps[upto]
    as_of = stage["when"]
    status = stage["board"][cid]
    plan = next((p for p in cycle.deploy_plan if p["change_id"] == cid), None) \
        if status == DEPLOYED else None
    sn_status = status_at(c, as_of, cycle.sn_updates.get(cid, []))   # ServiceNow Status
    cab_yes = happened(c["cab_approved_at"], as_of)
    p_yes = happened(c["approved_to_p_at"], as_of)
    if status == MOVED:
        state, cls = f"{sn_status} · rescheduled → {cycle.moved[cid]['target']}", "moved"
    else:
        state = sn_status
        cls = "ok" if sn_status in GOOD else "info"

    st.markdown(f'<div class="asof">Showing this record as of <b>{esc(stage["title"])}</b> · '
                f'{as_of:%a %d %b %Y %H:%M} IST in release <b>{esc(cycle.release_id)}</b></div>',
                unsafe_allow_html=True)

    st.markdown(f'<div class="rec-top"><div><div class="kind">Change Request</div>'
                f'<div class="num">{esc(cid)}</div></div>'
                f'<span class="rec-state {cls}">{esc(state)}</span></div>',
                unsafe_allow_html=True)

    start = plan["start"] if plan else cycle.cal["p_start"]
    end = plan["end"] if plan else cycle.cal["p_end"]
    left = [
        ("Number", f'<span class="mono">{esc(cid)}</span>'),
        ("Requested by", esc(c["requested_by"])),
        ("Configuration item", esc(c["application"])),
        ("System", f'<span class="mono">{esc(c["system"])}</span>'),
        ("Environment", esc(c["environment"])),
        ("Assignment group", esc(c["assignment_group"])),
        ("Assigned to", esc(c["assigned_to"])),
    ]
    status_cls = "ok-txt" if sn_status in GOOD else ""
    right = [
        ("Status", f'<span class="{status_cls}">{esc(sn_status)}</span>'),
        ("CAB approved", '<span class="ok-txt">Yes</span>' if cab_yes
         else '<span class="bad-txt">No</span>'),
        ("Approved to P", '<span class="ok-txt">Yes</span>' if p_yes
         else '<span class="bad-txt">No</span>'),
        ("Type", esc(c["change_type"])),
        ("Category", esc(c["work_type"])),
        ("Risk", esc(c["risk"])),
        ("Priority", esc(c["priority"])),
        ("Planned release", f'<span class="mono">{esc(c["requested_release"])}</span>'
         + (f' (carried over from <span class="mono">{esc(c["moved_from_release"])}</span>)'
            if c.get("moved_from_release") else "")),
        ("Planned start / end", f"{fmt(start)} – {fmt(end, '%H:%M')}"
         + ("" if plan else " (release window)")),
        ("Downtime", f"{c['downtime_minutes']} min" if c["downtime_required"] else "None"),
    ]

    def rows(pairs):
        return "".join(f'<div class="rec-row"><div class="k">{k}</div><div class="v">{v}</div>'
                       f'</div>' for k, v in pairs)

    desc = (f"{c['work_type']} on {c['application']} ({c['system']}), delivered through "
            f"the {c['release_type'].lower()} release {c['requested_release']}. "
            f"Estimated duration {c['duration_minutes']} minutes"
            + (f", including {c['downtime_minutes']} minutes of downtime." if
               c["downtime_required"] else ", no downtime.")
            + (f" Depends on {', '.join(c['depends_on'])}." if c["depends_on"] else ""))
    st.markdown(f'<div class="rec-body"><div class="rec-grid"><div>{rows(left)}</div>'
                f'<div>{rows(right)}</div></div>'
                f'<div class="rec-row" style="border:none;margin-top:6px"><div class="k">'
                f'Short description</div><div class="v"><b>{esc(c["short_description"])}</b>'
                f'</div></div><div class="rec-row" style="border:none"><div class="k">'
                f'Description</div><div class="v rec-desc">{esc(desc)}</div></div></div>',
                unsafe_allow_html=True)

    if status == MOVED:
        m = cycle.moved[cid]
        st.markdown(f'<div class="rec-sec" style="border-color:#FFC9C9;background:#FFF5F5">'
                    f'<h4 style="color:#C92A2A">Removed from release</h4><div class="rec-desc">'
                    f'<b>Stage:</b> {esc(m["stage"])} · <b>Reason:</b> {esc(m["reason"])} · '
                    f'<b>Policy:</b> <span class="mono">{esc(m["rule"])}</span> · '
                    f'<b>Moved to:</b> <span class="mono">{esc(m["target"])}</span></div></div>',
                    unsafe_allow_html=True)

    render_attachments(data, c, step)
    render_deployment_log(cycle, cid, upto)

    a, b = st.columns(2)
    with a:
        cab = "ECAB" if c["change_type"] == "Emergency" else "CAB"
        a_ok = cab_yes and sn_status != "New" and bool(c["tr_list"])
        p_ok = p_yes and sn_status in ("Ready for release", "Deployed to P", "Closed")
        who_sets = {"Requester": c["requested_by"], "Change owner": c["assigned_to"]}
        hist = "".join(f'<tr><td>{esc(h["status"])}</td><td>{fmt(h["at"])}</td>'
                       f'<td>{esc(who_sets.get(h["by"], h["by"]))}</td></tr>'
                       for h in cycle.status_history(cid) if happened(h["at"], as_of))
        st.markdown(
            '<div class="rec-sec"><h4>Release gates</h4><table class="rec-tbl">'
            '<tr><th>Gate</th><th>Needs</th><th>Now</th></tr>'
            f'<tr><td>Acceptance release</td><td>CAB approved = Yes and Status = In progress'
            f'</td><td>{yes_no(a_ok, "Met", "Not met")}</td></tr>'
            f'<tr><td>Production release</td><td>Approved to P = Yes and Status = Ready for '
            f'release</td><td>{yes_no(p_ok, "Met", "Not met")}</td></tr></table>'
            f'<div style="height:10px"></div><table class="rec-tbl">'
            f'<tr><th>{cab} approved</th><th>Recorded</th></tr>'
            f'<tr><td>{"Yes" if cab_yes else "No"}</td>'
            f'<td>{fmt(c["cab_approved_at"]) if cab_yes else "—"}</td></tr></table>'
            f'<div style="height:10px"></div><table class="rec-tbl">'
            f'<tr><th>Status history</th><th>Changed</th><th>By</th></tr>{hist}</table></div>',
            unsafe_allow_html=True)
        st.markdown(
            '<div class="rec-sec"><h4>Planning</h4><table class="rec-tbl">'
            f'<tr><td>Implementation plan</td><td>{yes_no(c["implementation_plan"])}</td></tr>'
            f'<tr><td>Backout plan</td><td>{yes_no(c["backout_plan"])}</td></tr>'
            f'<tr><td>Test evidence</td><td>{yes_no(c["test_evidence"])}</td></tr>'
            f'<tr><td>Downtime communication</td><td>'
            + ("Not required" if not c["downtime_required"] else
               yes_no(happened(c["downtime_comms_sent_at"], as_of),
                      f"Sent {fmt(c['downtime_comms_sent_at'])}", "Not sent yet"))
            + '</td></tr></table></div>', unsafe_allow_html=True)
    with b:
        deps = "".join(f'<tr><td>Depends on</td><td>{cr_link(d, step=step)}</td>'
                       f'<td>{esc(data.by_id[d]["application"])}</td></tr>'
                       for d in c["depends_on"] if d in data.by_id)
        deps += "".join(f'<tr><td>Required by</td><td>{cr_link(d, step=step)}</td>'
                        f'<td>{esc(data.by_id[d]["application"])}</td></tr>'
                        for d in dependents(data, cid))
        st.markdown('<div class="rec-sec"><h4>Related changes</h4>'
                    + (f'<table class="rec-tbl">{deps}</table>' if deps else
                       '<div class="rec-desc">No dependencies.</div>') + '</div>',
                    unsafe_allow_html=True)
        commits = "".join(f'<tr><td class="mono">{esc(x["sha"])}</td><td>{esc(x["message"])}'
                          f'</td></tr>' for x in c["commits"])
        st.markdown(f'<div class="rec-sec"><h4>Linked commits</h4><table class="rec-tbl">'
                    f'{commits}</table></div>', unsafe_allow_html=True)
        incs = [i for i in data.incidents if i["application"] == c["application"]][-3:]
        inc_rows = "".join(f'<tr><td class="mono">{esc(i["incident_id"])}</td>'
                           f'<td>{esc(i["priority"])}</td><td>{fmt(i["opened_at"], "%d %b")}</td>'
                           f'<td>{esc(i["short_description"])}</td></tr>' for i in incs)
        st.markdown('<div class="rec-sec"><h4>Recent incidents on this CI</h4>'
                    + (f'<table class="rec-tbl">{inc_rows}</table>' if incs else
                       '<div class="rec-desc">None in the last 4 months.</div>') + '</div>',
                    unsafe_allow_html=True)

    acts = "".join(f'<div class="act-item {kind}"><div class="t">{fmt(when)} · '
                   f'<span class="who">{esc(who)}</span></div>{text}</div>'
                   for when, kind, who, text in activity(data, cycle, c, upto, as_of))
    st.markdown(f'<div class="rec-sec"><h4>Activity</h4><div class="act">{acts}</div></div>',
                unsafe_allow_html=True)
    st.caption("Mock change record built from synthetic data (fictional company Orbitra "
               "Retail). Not connected to a real ITSM system.")
