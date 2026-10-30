"""
Release cycle engine: runs a weekly or monthly release from start to end.

The engine reads the ServiceNow ticket fields and attachments:
  - CAB approved (Yes/No) and Status = In progress  -> taken into the Acceptance release
  - Approved to P = Yes and Status = Ready for release -> taken into the Production release
  - Release note + TR list; dependencies come from the TR list

At each deployment it prepares the TR list for the deployment team (consolidated for A,
segregated for P), and records the deployment team's Status updates (Deployed to A,
Deployed to P), which move the change across the release console.

A change that fails a gate is moved out of the release (with the reason, the policy rule
and the release it moves to), and every change that depends on it goes with it.
The LLM never makes these decisions; it only explains them.
"""

from datetime import datetime, timedelta

from .data import parse
from .deploy_tools import DeploymentHub
from .release_calendar import (MONTHLY_WINDOW_MINUTES, calendar_for, next_monthly_after,
                               next_weekly_after)

PRIORITY_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

# Release console columns, named after the ServiceNow Status that puts a change there
WAITING = "New / not scoped"
IN_SCOPE = "In progress"
IN_A = "Deployed to A"
REG_OK = IN_A                      # regression passed: still on A, awaiting approval to P
APPROVED = "Ready for release"
DEPLOYED = "Deployed to P"
MOVED = "Moved out"
BOARD_COLUMNS = [WAITING, IN_SCOPE, IN_A, APPROVED, DEPLOYED, MOVED]


def status_at(c, moment, extra=()):
    """The ticket's ServiceNow Status at a moment (people's updates + deployment team's)."""
    current = None
    for h in sorted(list(c["status_history"]) + list(extra), key=lambda h: h["at"]):
        if parse(h["at"]) <= moment:
            current = h["status"]
    return current or "Not created"


def event(kind, text, change_id=None, rule=None, target=None):
    return {"kind": kind, "text": text, "change_id": change_id, "rule": rule,
            "target": target}


class ReleaseCycle:
    def __init__(self, data, release_id):
        self.data = data
        self.release_id = release_id
        self.cal = calendar_for(release_id)
        self.changes = [c for c in data.changes if c["requested_release"] == release_id]
        self.by_id = {c["change_id"]: c for c in self.changes}
        self.status = {c["change_id"]: WAITING for c in self.changes}
        self.moved = {}          # change_id -> {stage, reason, rule, target}
        self.sn_updates = {c["change_id"]: [] for c in self.changes}   # deployment team etc.
        self.handovers = {}      # step key -> TR list handed to the deployment team
        self.jobs = {}           # step key -> deployment tool jobs (Rev-Trac, pipeline)
        self.hub = DeploymentHub()
        self.reached_a = []      # changes that were deployed to A in this release
        self.deploy_plan = []
        self.steps = []
        self._run()

    # ----------------------------------------------------------- helpers
    def active(self):
        return [c for c in self.changes if self.status[c["change_id"]] not in (WAITING, MOVED)]

    def move(self, c, stage, reason, rule, target, events):
        cid = c["change_id"]
        self.status[cid] = MOVED
        self.moved[cid] = {"stage": stage, "reason": reason, "rule": rule, "target": target}
        events.append(event("moved", f"{reason} → moved to {target}", cid, rule, target))

    def cascade(self, stage, target, events):
        """DEP-01: pull every active change that depends on a moved-out change."""
        changed = True
        while changed:
            changed = False
            for c in self.active():
                blocked = [d for d in c["depends_on"] if d in self.moved]
                if blocked:
                    self.move(c, stage, f"Depends on {blocked[0]} (per its TR list), which "
                              "was moved out", "DEP-01", target, events)
                    changed = True

    def snapshot(self, key, title, when, subtitle, events):
        self.steps.append({"key": key, "title": title, "when": when, "subtitle": subtitle,
                           "events": events, "board": dict(self.status)})

    def sn_set(self, c, status, at, by):
        self.sn_updates[c["change_id"]].append(
            {"status": status, "at": at.isoformat(timespec="minutes"), "by": by})

    def status_history(self, cid):
        c = self.data.by_id[cid]
        return sorted(list(c["status_history"]) + self.sn_updates.get(cid, []),
                      key=lambda h: h["at"])

    def freeze_hit(self, c, start, end):
        for z in self.data.freezes:
            covers = z["scope"] == "all" or \
                (z["scope"] == "tier" and c["application_tier"] in z.get("tiers", [])) or \
                (z["scope"] == "applications" and c["application"] in z.get("applications", []))
            if covers and start < parse(z["end"]) and parse(z["start"]) < end \
                    and not c.get("freeze_exception"):
                return z
        return None

    def acceptance_problem(self, c, cutoff):
        """Gate into the Acceptance release. Returns (reason, kind): 'gate' or 'plan'."""
        if c["cab_approved"] != "Yes" or parse(c["cab_approved_at"]) > cutoff:
            return "CAB approved = No at the cutoff", "gate"
        status = status_at(c, cutoff)
        if status not in ("In progress", "Deployed to A"):
            return f"Status is {status}, not In progress, at the cutoff", "gate"
        if not c["release_note"] or not c["tr_list"]:
            return "No release note / TR list attached to the change", "plan"
        if not c["implementation_plan"]:
            return "No implementation plan in ServiceNow", "plan"
        if c["risk"] in ("Moderate", "High") and not c["backout_plan"]:
            return f"{c['risk']}-risk change without a backout plan", "plan"
        return None, None

    def already_on_a(self, c, moment, ev, rule):
        """A change whose Status is already Deployed to A (carried over from an earlier
        release) is not deployed to A again and is left out of the A TR list."""
        if status_at(c, moment) != "Deployed to A":
            return False
        self.status[c["change_id"]] = IN_A
        self.reached_a.append(c)
        origin = f" (carried over from {c['moved_from_release']})" \
            if c.get("moved_from_release") else ""
        ev.append(event("info", f"Status already Deployed to A{origin}: not included in the "
                                "A TR list and not redeployed; still needs Approved to P",
                        c["change_id"], rule))
        return True

    def production_problem(self, c, deadline):
        """Gate into the Production release: Approved to P = Yes, Status Ready for release."""
        if c["approved_to_p"] != "Yes" or parse(c["approved_to_p_at"]) > deadline:
            return "Not approved by user (Approved to P = No)"
        if status_at(c, deadline) != "Ready for release":
            return "Approved to P = Yes, but Status not set to Ready for release"
        return None

    # ------------------------------------------------------------ TR lists
    def dependency_order(self, changes):
        ids, seen, out = {c["change_id"] for c in changes}, set(), []

        def visit(c):
            if c["change_id"] in seen:
                return
            seen.add(c["change_id"])
            for d in c["depends_on"]:
                if d in ids:
                    visit(self.by_id[d])
            out.append(c)

        for c in sorted(changes, key=lambda c: (PRIORITY_RANK[c["priority"]],
                                                c["submitted_at"])):
            visit(c)
        return out

    def tr_rows(self, changes, env):
        rows, n = [], 0
        for c in self.dependency_order(changes):
            for t in sorted(c["tr_list"], key=lambda t: t["sequence"]):
                n += 1
                rows.append({"Seq": n, "TR": t["tr_id"], "Change": c["change_id"],
                             "Application": c["application"], "Type": t["type"],
                             "Target": t["a_target"] if env == "A" else t["p_target"],
                             "Import after": t["depends_on_tr"] or "",
                             "Description": t["description"]})
        return rows

    def handover(self, key, env, title, when, changes, excluded=(), events=None, rule=None):
        rows = self.tr_rows(changes, env)
        excl = []
        for c, reason in excluded:
            for t in c["tr_list"]:
                excl.append({"TR": t["tr_id"], "Change": c["change_id"],
                             "Application": c["application"], "Reason": reason})
        self.handovers[key] = {"env": env, "title": title, "when": when, "rows": rows,
                               "excluded": excl, "changes": [c["change_id"] for c in changes]}
        if events is not None and changes:
            what = "Consolidated" if env == "A" else "Segregated"
            extra = f"; {len(excl)} TRs listed as do-not-deploy" if excl else ""
            events.insert(0, event("info", f"{what} TR list for {env} prepared "
                                   f"from the change tickets: {len(rows)} TR(s) from {len(changes)} change(s)"
                                   f"{extra}",
                                   None, rule))

    def schedule(self, changes, start, window_end):
        """Cutover plan: one change at a time per system, dependencies first."""
        free, ends, plan = {}, {}, []
        for c in self.dependency_order(changes):
            s = max([start, free.get(c["system"], start)] +
                    [ends[d] for d in c["depends_on"] if d in ends])
            e = s + timedelta(minutes=c["duration_minutes"])
            free[c["system"]], ends[c["change_id"]] = e, e
            plan.append({"change_id": c["change_id"], "application": c["application"],
                         "system": c["system"], "start": s, "end": e,
                         "downtime": c["downtime_minutes"],
                         "depends_on": [d for d in c["depends_on"] if d in ends],
                         "fits": e <= window_end})
        return sorted(plan, key=lambda p: (p["start"], p["system"]))

    def _send(self, key, rows, env, start, ev, rule, timing=None, failing=None):
        """Hand the TR list to Rev-Trac / the CI/CD pipeline and keep the jobs."""
        jobs = self.hub.deploy(rows, env, start, failing or {}, timing)
        self.jobs[key] = jobs
        if jobs:
            sent = " and ".join(f"{j['tool']} (job {j['job_id']}, {len(j['results'])} TRs)"
                                for j in jobs)
            ev.append(event("info", f"TR list for {env} sent to {sent}", None, "TRH-05"))
        return jobs

    @staticmethod
    def _results_for(jobs, cid):
        return [(j, r) for j in jobs for r in j["results"] if r["Change"] == cid]

    def _confirm(self, c, jobs, env, stage, rule, target, ev):
        """Read the tool's confirmation. All TRs RC <= 4: set the ServiceNow Status
        automatically. Any TR RC >= 8: the change failed its deployment."""
        results = self._results_for(jobs, c["change_id"])
        failed = [(j, r) for j, r in results if r["Result"] == "Failed"]
        if failed:
            j, r = failed[0]
            return False, f"{j['tool']} import failed: {r['TR']} RC {r['RC']} ({r['Message']})"
        done = max(r["Finished"] for _, r in results)
        tools = " + ".join(sorted({j["tool"] for j, _ in results}))
        worst = max(r["RC"] for _, r in results)
        status = f"Deployed to {env}"
        self.sn_set(c, status, done, f"{tools} integration")
        warn = " with warnings" if worst == 4 else ""
        ev.append(event("ok", f"{tools} confirmed {len(results)} TR(s) imported{warn} "
                              f"(max RC {worst}) → Status set to {status} automatically at "
                              f"{done:%H:%M}", c["change_id"], rule))
        return True, None

    def deploy_to_a(self, changes, start, stage, rule, target, ev, key):
        """Send the consolidated TR list to the tools; confirmations drive the Status."""
        failing = {c["change_id"]: c["a_deploy_note"] for c in changes
                   if c["a_deploy_result"] == "failed"}
        jobs = self._send(key, self.tr_rows(changes, "A"), "A", start, ev, "TRH-05",
                          failing=failing)
        for c in self.dependency_order(changes):
            ok, why = self._confirm(c, jobs, "A", stage, rule, target, ev)
            if ok:
                self.status[c["change_id"]] = IN_A
                self.reached_a.append(c)
            else:
                self.move(c, stage, f"{why}; Status left In progress", rule, target, ev)

    def deploy_to_p(self, rule, ev, key="production"):
        """Send the segregated TR list; the plan's slots set when each change is imported."""
        changes = [self.by_id[p["change_id"]] for p in self.deploy_plan]
        timing = {p["change_id"]: (p["start"], p["end"]) for p in self.deploy_plan}
        jobs = self._send(key, self.tr_rows(changes, "P"), "P", self.cal["p_start"], ev,
                          "TRH-05", timing=timing)
        for p in self.deploy_plan:
            c = self.by_id[p["change_id"]]
            ok, _ = self._confirm(c, jobs, "P", "P deployment", rule, None, ev)
            if ok:
                self.status[c["change_id"]] = DEPLOYED
            if not p["fits"]:
                ev.append(event("warn", "Runs past the end of the window", c["change_id"],
                                rule))

    def p_handover(self, key, when, rule, ev):
        approved = self.active()
        excluded = [(c, self.moved[c["change_id"]]["reason"]) for c in self.reached_a
                    if c["change_id"] in self.moved]
        self.handover(key, "P", f"Segregated TR list for P · {when:%a %d %b}", when, approved,
                      excluded, ev, rule)

    def _run(self):
        (self._run_weekly if self.cal["type"] == "Weekly" else self._run_monthly)()

    # ------------------------------------------------------------- weekly
    def _run_weekly(self):
        cal = self.cal
        nxt = next_weekly_after(cal["p_start"])
        days = cal["intake_days"]

        def at(d, h, m=0):
            return datetime.combine(d, datetime.min.time()).replace(hour=h, minute=m)

        def entry_day(c):
            t = parse(c["submitted_at"])
            for d in days:
                if t <= at(d, 15):
                    return d
            return None

        late_by_day = {}
        for c in self.changes:
            if entry_day(c) is None:
                d = parse(c["submitted_at"]).date()
                late_by_day.setdefault(min(d, days[-1]), []).append(c)

        for d in days:
            ev, accepted = [], []
            for c in sorted([c for c in self.changes if entry_day(c) == d],
                            key=lambda c: c["submitted_at"]):
                cid, t = c["change_id"], parse(c["submitted_at"])
                self.status[cid] = IN_SCOPE
                if c["downtime_required"] or c["depends_on"]:
                    why = "needs downtime" if c["downtime_required"] else \
                        f"its TR list depends on {', '.join(c['depends_on'])}"
                    self.move(c, "Intake", f"Not eligible for the weekly release: {why}",
                              "WRC-01", next_monthly_after(t), ev)
                    continue
                z = self.freeze_hit(c, cal["p_start"], cal["p_end"])
                if z:
                    self.move(c, "Intake", f"P window falls in freeze {z['id']} ({z['name']})",
                              "FRZ-P02", next_weekly_after(parse(z["end"])), ev)
                    continue
                problem, kind = self.acceptance_problem(c, at(d, 15))
                if problem:
                    self.move(c, "Intake", problem, "WRC-02" if kind == "gate" else "CHG-04",
                              nxt, ev)
                    continue
                if self.already_on_a(c, at(d, 15), ev, "WRC-02"):
                    continue
                since = f"{t:%a %H:%M}" if t.date() == d else f"{t:%a %d %b %H:%M}"
                ev.append(event("info", f"Taken into A: CAB approved = Yes, Status In progress "
                                        f"since {since}", cid, "WRC-02"))
                accepted.append(c)
            self.handover(f"intake-{d:%a}", "A", f"Consolidated TR list for A · {d:%a %d %b}",
                          at(d, 15, 10), accepted, events=ev, rule="TRH-03")
            self.deploy_to_a(accepted, at(d, 16), "A deployment", "WRC-03", nxt, ev,
                             key=f"intake-{d:%a}")
            for c in late_by_day.get(d, []):
                t = parse(c["submitted_at"])
                self.status[c["change_id"]] = IN_SCOPE
                self.move(c, "Intake", f"Status In progress only from {t:%a %H:%M}, after "
                          "the final Thursday 15:00 cutoff", "WRC-02", nxt, ev)
            if not ev:
                ev.append(event("info", "No new changes today."))
            self.snapshot(f"intake-{d:%a}", f"{d:%A} intake", at(d, 18),
                          "Cutoff 15:00 IST · TR list to deployment team · A deployment 16:00",
                          ev)

        # Friday: regression + approvals + segregated TR list for P
        fri = cal["approval_deadline"]
        ev = [event("info", "No A deployments today: regression testing and approvals.")]
        for c in self.active():
            if c["regression_result"] == "failed":
                self.move(c, "Regression", f"Failed regression: {c['regression_note']}",
                          "WRC-04", nxt, ev)
        for c in self.active():
            problem = self.production_problem(c, fri)
            if problem:
                self.move(c, "Approvals", f"{problem} by Friday 18:00", "WRC-05", nxt, ev)
            else:
                self.status[c["change_id"]] = APPROVED
                ev.append(event("ok", "Regression passed; Approved to P = Yes, Status Ready "
                                      "for release", c["change_id"], "WRC-05"))
        self.p_handover("friday", fri, "TRH-04", ev)
        self.snapshot("friday", "Friday: regression & approvals", fri,
                      "No A deployments · approval deadline 18:00 · TR list for P", ev)

        # Saturday: P deployment
        ev = []
        self.deploy_plan = self.schedule(self.active(), cal["p_start"], cal["p_end"])
        self.deploy_to_p("WRC-06", ev)
        if not ev:
            ev.append(event("warn", "Nothing left to deploy."))
        self.snapshot("production", "Saturday: P deployment", cal["p_start"],
                      "Production window 08:00–10:00 IST", ev)
        self._closure()

    # ------------------------------------------------------------ monthly
    def _run_monthly(self):
        cal = self.cal
        nxt = next_monthly_after(cal["d1"] + timedelta(minutes=1))

        ev = []
        for c in sorted(self.changes, key=lambda c: c["submitted_at"]):
            self.status[c["change_id"]] = IN_SCOPE
            t = parse(c["submitted_at"])
            if t > cal["d1"]:
                self.move(c, "D1", f"Status In progress only from {t:%a %d %b %H:%M}, after D1",
                          "MRC-02", nxt, ev)
                continue
            problem, kind = self.acceptance_problem(c, cal["d1"])
            if problem:
                self.move(c, "D1", problem, "MRC-02" if kind == "gate" else "CHG-04", nxt, ev)
            else:
                ev.append(event("ok", "CAB approved = Yes and Status In progress before D1",
                                c["change_id"], "MRC-02"))
        self.cascade("D1", nxt, ev)
        self.snapshot("d1", "D1: ready in ServiceNow", cal["d1"],
                      f"Deadline {cal['d1']:%a %d %b} 23:59 IST", ev)

        ev = [event("info", f"{len(self.active())} changes extracted from ServiceNow with their "
                            "release notes and TR lists. Release scope is frozen.")]
        used = {}
        for c in sorted(self.active(), key=lambda c: (PRIORITY_RANK[c["priority"]],
                                                       c["submitted_at"])):
            total = used.get(c["system"], 0) + c["duration_minutes"]
            if total > MONTHLY_WINDOW_MINUTES:
                self.move(c, "Extraction",
                          f"Does not fit the 6h window on {c['system']} "
                          f"({used[c['system']]} min already planned + "
                          f"{c['duration_minutes']} min)", "MRC-04", nxt, ev)
            else:
                used[c["system"]] = total
        self.cascade("Extraction", nxt, ev)
        deps = sum(1 for c in self.active() if c["depends_on"])
        ev.append(event("info", f"{deps} dependencies found in the TR lists; TRs will be "
                                "imported in dependency order.", None, "TRH-02"))
        self.snapshot("extraction", "Extraction: scope frozen", cal["extraction"],
                      "Changes downloaded from ServiceNow · window capacity checked", ev)

        ev = []
        scoped = [c for c in self.active()
                  if not self.already_on_a(c, cal["a_deploy"], ev, "MRC-05")]
        self.handover("a-deploy", "A", f"Consolidated TR list for A · {cal['a_deploy']:%a %d %b}",
                      cal["a_deploy"], scoped, events=ev, rule="TRH-03")
        self.deploy_to_a(scoped, cal["a_deploy"], "A deployment", "MRC-05", nxt, ev,
                         key="a-deploy")
        self.cascade("A deployment", nxt, ev)
        self.snapshot("a-deploy", "Acceptance deployment", cal["a_deploy"] + timedelta(hours=4),
                      f"{cal['a_deploy']:%A %d %b} · TR list to deployment team · regression "
                      "starts", ev)

        for week, when in ((1, cal["regression_mid"]),
                           (2, cal["go_no_go"] - timedelta(hours=12))):
            ev = []
            for c in self.active():
                if c["regression_result"] == "failed" and c.get("regression_fail_week") == week:
                    self.move(c, f"Regression week {week}",
                              f"Failed regression: {c['regression_note']}", "MRC-06", nxt, ev)
            self.cascade(f"Regression week {week}", nxt, ev)
            if week == 2:
                ev.append(event("ok", f"{len(self.active())} changes passed regression."))
            elif not ev:
                ev.append(event("info", "No regression defects this week."))
            self.snapshot(f"regression-{week}", f"Regression week {week}", when,
                          "Testing on Acceptance", ev)

        ev = []
        for c in self.active():
            problem = self.production_problem(c, cal["go_no_go"])
            if problem:
                self.move(c, "Go/No-Go", problem, "MRC-07", nxt, ev)
                continue
            if c["downtime_required"] and (not c["downtime_comms_sent_at"] or
                                           parse(c["downtime_comms_sent_at"]) >
                                           cal["comms_deadline"]):
                self.move(c, "Go/No-Go", "Downtime communication not sent 48h before P",
                          "DWN-02", nxt, ev)
                continue
            self.status[c["change_id"]] = APPROVED
        self.cascade("Go/No-Go", nxt, ev)
        for c in self.active():
            ev.append(event("ok", "GO: Approved to P = Yes, Status Ready for release",
                            c["change_id"], "MRC-07"))
        self.p_handover("go-no-go", cal["go_no_go"], "TRH-04", ev)
        self.snapshot("go-no-go", "Go/No-Go", cal["go_no_go"],
                      "Approvals by 12:00 · downtime comms 48h before P · TR list for P", ev)

        ev = []
        self.deploy_plan = self.schedule(self.active(), cal["p_start"], cal["p_end"])
        self.deploy_to_p("MRC-08", ev)
        self.snapshot("production", "P deployment (downtime window)", cal["p_start"],
                      "Sunday 00:00–06:00 IST", ev)
        self._closure()

    # ------------------------------------------------------------ closure
    def _closure(self):
        deployed = [c for c in self.changes if self.status[c["change_id"]] == DEPLOYED]
        for c in deployed:
            self.sn_set(c, "Closed", self.cal["p_end"] + timedelta(hours=1), "Release Manager")
        ev = [event("info", f"{len(deployed)} of {len(self.changes)} changes deployed to "
                            f"Production and closed; {len(self.moved)} moved out.")]
        for cid, m in self.moved.items():
            ev.append(event("moved", f"{m['stage']}: {m['reason']} → {m['target']}",
                            cid, m["rule"], m["target"]))
        self.snapshot("closure", "Release closure", self.cal["p_end"] + timedelta(hours=1),
                      "Summary for CAB and management", ev)

    # ------------------------------------------------------------ summary
    def summary(self):
        return {
            "release_id": self.release_id,
            "name": self.cal["name"],
            "type": self.cal["type"],
            "requested": len(self.changes),
            "deployed": [cid for cid, s in self.status.items() if s == DEPLOYED],
            "moved_out": self.moved,
            "deploy_plan": [{**p, "start": p["start"].strftime("%a %d %b %H:%M"),
                             "end": p["end"].strftime("%H:%M")} for p in self.deploy_plan],
            "deployment_jobs": {k: [{"tool": j["tool"], "job_id": j["job_id"],
                                     "failed": [f"{r['TR']} RC {r['RC']}" for r in j["results"]
                                                if r["Result"] == "Failed"]}
                                    for j in js] for k, js in self.jobs.items()},
            "tr_handovers": {k: {"title": h["title"], "trs": len(h["rows"]),
                                 "changes": h["changes"],
                                 "do_not_deploy": sorted({x["Change"] for x in h["excluded"]})}
                             for k, h in self.handovers.items()},
        }


# ------------------------------------------------------------ dependencies
def dependents(data, change_id):
    return [c["change_id"] for c in data.changes if change_id in c["depends_on"]]


def upstream_chain(data, change_id, seen=None):
    seen = seen if seen is not None else []
    for d in data.by_id[change_id]["depends_on"]:
        if d not in seen and d in data.by_id:
            seen.append(d)
            upstream_chain(data, d, seen)
    return seen


def delay_impact(data, change_id):
    impacted, frontier = [], [change_id]
    while frontier:
        cid = frontier.pop(0)
        for d in dependents(data, cid):
            if d not in [i["change_id"] for i in impacted]:
                impacted.append({"change_id": d, "via": cid,
                                 "application": data.by_id[d]["application"]})
                frontier.append(d)
    return impacted
