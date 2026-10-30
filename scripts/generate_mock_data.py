"""
Synthetic data for the AI-Driven Change and Release Management Assistant.

Fictional company "Orbitra Retail". All data is made up.

Two demo releases are scripted so the demo tells the same story every time:
  WR-2026-1010  weekly release, P on Sat 10 Oct 2026 08:00-10:00 IST
  MR-2026-10    monthly release, P on Sun 25 Oct 2026 00:00-06:00 IST
Other releases in October/November are filled with clean, randomised changes.

Outputs (data/):
  applications.json, releases.json, change_requests.json, incidents.json,
  freeze_windows.json, planted_scenarios.json (answer key for tests only)
  attachments/CR-xxxx/   Release_Note_CR-xxxx.docx and TR_List_CR-xxxx.xlsx per change

Usage:  python scripts/generate_mock_data.py [--seed 42]
"""

import argparse
import json
import random
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from release_assistant.attachments import write_attachments  # noqa
from release_assistant.release_calendar import (calendar_for, monthly_calendar,  # noqa
                                                weekly_calendar, weekly_id)

DATA_DIR = ROOT / "data"

# scenarios that leave the release before the user can approve to P
EARLY_EXIT_RULES = {"WRC-01", "WRC-02", "WRC-03", "WRC-04", "CHG-04",
                    "MRC-02", "MRC-04", "MRC-05", "MRC-06"}

APPLICATIONS = [
    ("APP-001", "Customer Portal", 1, "Digital Channels", ["portal-web-prod"]),
    ("APP-002", "Payments Gateway", 1, "Payments", ["payments-api-prod", "ora-prd-db-01"]),
    ("APP-003", "Order Management", 1, "Commerce Core", ["oms-app-prod", "ora-prd-db-01"]),
    ("APP-004", "Inventory API", 2, "Supply Chain", ["inventory-api-prod", "pg-prd-db-02"]),
    ("APP-005", "Auth Service", 1, "Platform Security", ["auth-idp-prod"]),
    ("APP-006", "Notification Service", 2, "Platform", ["notify-prod", "kafka-prd-cluster"]),
    ("APP-007", "Mobile App Backend", 1, "Digital Channels", ["mobile-bff-prod"]),
    ("APP-008", "Reporting Warehouse", 3, "Data & Analytics", ["dwh-prod"]),
    ("APP-009", "HR Portal", 3, "Corporate IT", ["hr-portal-prod"]),
    ("APP-010", "Search Service", 2, "Commerce Core", ["search-prod"]),
    ("APP-011", "CRM Integration", 2, "Customer Ops", ["crm-integration-prod"]),
    ("APP-012", "Pricing Engine", 1, "Commerce Core", ["pricing-prod"]),
    ("APP-013", "SAP S/4HANA Finance", 1, "SAP Finance", ["SAP-S4P"]),
    ("APP-014", "SAP EWM Logistics", 2, "SAP Logistics", ["SAP-EWP"]),
    ("APP-015", "SAP HANA Platform", 1, "System Cleaning Team", ["SAP-HANA-PRD-DB"]),
]
APP = {a[1]: a for a in APPLICATIONS}
PEOPLE = ["Ananya Rao", "Rahul Menon", "Priya Iyer", "Vikram Shetty", "Sneha Kulkarni",
          "Arjun Nair", "Lena Fischer", "Tobias Weber", "Meera Joshi", "Karthik Reddy",
          "Divya Pillai", "Jonas Becker", "Farah Siddiqui", "Rohan Das", "Nisha Hegde"]
RELEASE_MANAGERS = ["Sophie Wagner", "Aditya Kulkarni", "Neha Bhat"]
ENHANCEMENTS = ["loyalty points summary", "order tracking timeline", "invoice PDF layout",
                "address autofill", "search filters", "push notification templates",
                "refund status page", "wishlist sharing", "price alert emails",
                "stock level badge", "login page accessibility", "report scheduling"]


def dt(s):
    return datetime.fromisoformat(s)


def iso(d):
    return d.isoformat(timespec="minutes") if d else None


class Builder:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.n = 2000
        self.changes, self.planted, self.incidents = [], [], []

    def sha(self):
        return "".join(self.rng.choice("0123456789abcdef") for _ in range(7))

    def add(self, release, app_name, desc, submitted, *, work_type="Enhancement",
            change_type="Normal", risk="Low", priority=None, system=None, duration=30,
            downtime=0, depends_on=(), technical="approved", cab="approved",
            cab_at=None, user="approved", user_at=None, comms_at=None, status="In progress",
            rfr=True, trs=True, on_a_since=None, moved_from=None,
            impl=True, backout=True, a_result="success", a_note=None,
            reg_result="passed", reg_week=None, reg_note=None, expect=None):
        app_id, name, tier, team, systems = APP[app_name]
        self.n += self.rng.randint(1, 4)
        submitted = dt(submitted)
        cid = f"CR-{self.n}"
        cab_default, user_default = self.approval_times(release, submitted, change_type)
        if expect and expect[0] == "Moved out" and expect[1] in EARLY_EXIT_RULES:
            user = "pending"               # moved out before the user could test on A
        approved_at = (dt(user_at) if user_at else user_default) if user == "approved" \
            else None
        sys_name = system or systems[0]
        tr_list = self.tr_list(cid, sys_name, desc, depends_on) if trs else []
        if priority is None:
            priority = "Critical" if change_type == "Emergency" else \
                "High" if (risk == "High" or (tier == 1 and downtime)) else \
                "Medium" if (risk == "Moderate" or tier == 1) else "Low"
        rec = {
            "change_id": cid,
            "requested_release": release,
            "release_type": "Weekly" if release.startswith("WR") else "Monthly",
            "short_description": desc,
            "application_id": app_id, "application": name, "application_tier": tier,
            "system": sys_name,
            "work_type": work_type,
            "change_type": change_type,
            "risk": risk, "priority": priority,
            "environment": "Production",
            "requested_by": self.rng.choice(PEOPLE),
            "assigned_to": self.rng.choice(PEOPLE),
            "assignment_group": team,
            # time the ticket's Status moved to "In progress" (or was created, if still New)
            "submitted_at": iso(submitted),
            "cab_approved": "Yes" if cab == "approved" else "No",
            "cab_approved_at": iso(dt(cab_at) if cab_at else cab_default)
            if cab == "approved" else None,
            "approved_to_p": "Yes" if approved_at else "No",
            "approved_to_p_at": iso(approved_at),
            "status_history": self.status_history(submitted, status, approved_at, rfr,
                                                  on_a_since),
            "moved_from_release": moved_from,
            "downtime_required": downtime > 0,
            "downtime_minutes": downtime,
            "duration_minutes": max(duration, downtime),
            "downtime_comms_sent_at": comms_at if downtime else None,
            "release_note": self.release_note(cid, release, name, desc, downtime, tr_list)
            if trs else None,
            "tr_list": tr_list,
            "implementation_plan": impl, "backout_plan": backout, "test_evidence": True,
            "freeze_exception": None,
            "a_deploy_result": a_result, "a_deploy_note": a_note,
            "regression_result": reg_result, "regression_fail_week": reg_week,
            "regression_note": reg_note,
            "commits": [{"sha": self.sha(), "message": m} for m in
                        (f"feat: {desc.split(':')[-1].strip().lower()}",
                         "test: regression suite update",
                         "docs: runbook and backout steps")[:self.rng.randint(2, 3)]],
        }
        self.changes.append(rec)
        if expect:
            outcome, rule, scenario = expect
            self.planted.append({"change_id": cid, "release": release, "scenario": scenario,
                                 "expected_outcome": outcome, "expected_rule": rule})
        return cid

    def approval_times(self, release, submitted, change_type):
        """CAB approves at its Mon/Wed 11:00 meeting before the ticket goes In progress
        (ECAB 30 min before, for emergencies); the user sets Ready for release after
        testing on Acceptance."""
        cal = calendar_for(release)
        slot = timedelta(minutes=30 * (self.n % 8))      # spread sign-offs over the day
        if change_type == "Emergency":
            cab = submitted - timedelta(minutes=30)
        else:
            cab = submitted.replace(hour=11, minute=0)
            if cab > submitted:
                cab -= timedelta(days=1)
            while cab.weekday() not in (0, 2):             # CAB meets Mon and Wed
                cab -= timedelta(days=1)
        if cal["type"] == "Weekly":
            user = cal["approval_deadline"].replace(hour=12, minute=0) + slot
        else:
            user = (cal["go_no_go"] - timedelta(days=1)).replace(hour=10, minute=0) + slot
        return cab, user

    def status_history(self, submitted, status, approved_at, rfr, on_a_since=None):
        """Status changes made by people. The deployment team's updates (Deployed to A,
        Deployed to P) happen during the release cycle and are added by the engine."""
        created = submitted - timedelta(days=2, hours=3)
        if status == "New":
            return [{"status": "New", "at": iso(submitted), "by": "Requester"}]
        hist = [{"status": "New", "at": iso(created), "by": "Requester"},
                {"status": "In progress", "at": iso(submitted), "by": "Change owner"}]
        if on_a_since:          # deployed to A in an earlier release, then carried over
            hist.append({"status": "Deployed to A", "at": on_a_since, "by": "Deployment team"})
        if approved_at and rfr:
            hist.append({"status": "Ready for release",
                         "at": iso(approved_at + timedelta(minutes=15)), "by": "Change owner"})
        return hist

    # ------------------------------------------------ release note & TR list
    def tr_list(self, cid, system, desc, depends_on):
        """Transport requests attached to the change. Deterministic from the change number,
        so change IDs stay stable. A dependency is expressed on the first TR."""
        num = int(cid.split("-")[1])
        sap_prefix = {"SAP-S4P": ("S4DK9", "SAP-S4Q"), "SAP-EWP": ("EWDK9", "SAP-EWQ"),
                      "SAP-HANA-PRD-DB": ("HDBK9", "SAP-HANA-QAS-DB")}
        count = 1 + num % 3 if system in sap_prefix else 1 + num % 2
        kinds = (["Workbench", "Customizing", "Workbench"] if system in sap_prefix
                 else ["Application package", "Configuration package"])
        out = []
        for i in range(count):
            if system in sap_prefix:
                prefix, a_sys = sap_prefix[system]
                tr_id = f"{prefix}{(num * 37 + i * 101) % 100000:05d}"
            else:
                code = system.split("-")[0].upper()[:6]
                tr_id = f"TR-{code}-{(num * 13 + i * 7) % 10000:04d}"
                a_sys = system.replace("-prod", "-acc").replace("-prd-", "-acc-")
            kind = kinds[i % len(kinds)]
            out.append({"tr_id": tr_id, "sequence": i + 1, "type": kind,
                        "description": f"{desc.split(':')[-1].strip()} ({kind.lower()})",
                        "a_target": a_sys, "p_target": system, "depends_on_tr": None})
        if depends_on and out:
            parent = next(c for c in self.changes if c["change_id"] == depends_on[0])
            out[0]["depends_on_tr"] = parent["tr_list"][-1]["tr_id"]
        return out

    def release_note(self, cid, release, app_name, desc, downtime, tr_list):
        deps = [t for t in tr_list if t["depends_on_tr"]]
        dep_text = "None." if not deps else "; ".join(
            f"{t['tr_id']} must be imported after {t['depends_on_tr']} "
            f"({self.tr_owner(t['depends_on_tr'])})" for t in deps)
        return {
            "title": f"Release note {cid}: {desc}",
            "summary": f"{desc} for {app_name}, planned for {release}.",
            "deployment_steps": [f"Import {t['tr_id']} ({t['type']}) into {t['a_target']} "
                                 f"(A) / {t['p_target']} (P)" for t in tr_list]
            + ["Run smoke test and confirm in the change ticket"],
            "dependencies": dep_text,
            "downtime": f"{downtime} minutes" if downtime else "No downtime",
            "rollback": "Re-import the previous transport versions and follow the backout plan "
                        "attached to the change.",
        }

    def tr_owner(self, tr_id):
        for c in self.changes:
            if any(t["tr_id"] == tr_id for t in c["tr_list"]):
                return c["change_id"]
        return "?"

    # ------------------------------------------------ demo weekly release
    def demo_weekly(self):
        R = "WR-2026-1010"
        ok = ("Deployed to P", None)
        self.add(R, "Search Service", "Enhancement: search filters for size and colour",
                 "2026-10-02T17:10", expect=(*ok, "Ready last Friday, enters Monday's A"))
        self.add(R, "Customer Portal", "Enhancement: address autofill at checkout",
                 "2026-10-05T10:20", duration=40, risk="Moderate",
                 expect=(*ok, "Clean enhancement"))
        self.add(R, "Payments Gateway", "Enhancement: clearer UPI retry message",
                 "2026-10-05T11:30", expect=(*ok, "Clean enhancement"))
        self.add(R, "Notification Service", "Enhancement: push notification templates",
                 "2026-10-05T14:10", expect=(*ok, "Accepted 50 min before cutoff"))
        self.add(R, "Mobile App Backend", "Enhancement: order tracking timeline",
                 "2026-10-06T11:00", risk="Moderate", a_result="failed",
                 a_note="deployment script error on the A cluster",
                 expect=("Moved out", "WRC-03", "A deployment failure"))
        self.add(R, "Pricing Engine", "Config change: price alert threshold",
                 "2026-10-06T16:30",
                 expect=(*ok, "Missed Tuesday's cutoff, rolls into Wednesday's A"))
        self.add(R, "Auth Service", "Emergency fix: SSO token expiry defect",
                 "2026-10-07T09:40", change_type="Emergency", work_type="Emergency fix",
                 risk="Moderate", duration=20, expect=(*ok, "Emergency fix via weekly release"))
        self.add(R, "Reporting Warehouse", "Enhancement: report scheduling",
                 "2026-10-07T10:00", expect=(*ok, "Clean enhancement"))
        inv = self.add(R, "Inventory API", "Stock reservation index rebuild",
                       "2026-10-07T12:00", work_type="Downtime change", downtime=30,
                       risk="Moderate",
                       expect=("Moved out", "WRC-01", "Downtime change sent to weekly"))
        self.add(R, "CRM Integration", "Enhancement: address validation v2",
                 "2026-10-07T13:15", depends_on=[inv],
                 expect=("Moved out", "WRC-01", "Dependent change sent to weekly"))
        self.add(R, "Inventory API", "Enhancement: low-stock alert badge",
                 "2026-10-08T10:15", expect=(*ok, "Clean enhancement"))
        self.add(R, "HR Portal", "Enhancement: leave balance widget", "2026-10-08T12:30",
                 reg_result="failed", reg_note="leave balance mismatch for part-time staff",
                 expect=("Moved out", "WRC-04", "Regression failure"))
        self.add(R, "Order Management", "Enhancement: refund status email",
                 "2026-10-08T14:50", risk="Moderate", user="pending",
                 expect=("Moved out", "WRC-05", "User approval not given by Friday"))
        self.add(R, "Customer Portal", "Enhancement: wishlist sharing", "2026-10-08T15:40",
                 expect=("Moved out", "WRC-02", "Ready after the Thursday 15:00 cutoff"))

    # ----------------------------------------------- demo monthly release
    def demo_monthly(self):
        R = "MR-2026-10"
        ok = ("Deployed to P", None)
        comms = "2026-10-21T10:00"
        sps = self.add(R, "SAP S/4HANA Finance", "SAP support package stack SPS14",
                       "2026-09-24T11:00", work_type="Downtime change", risk="High",
                       downtime=180, comms_at=comms, expect=(*ok, "SAP SPS, 3h downtime"))
        tr = self.add(R, "SAP EWM Logistics", "SAP transport: goods receipt enhancement",
                      "2026-09-29T15:00", work_type="Project deployment", risk="Moderate",
                      duration=45, depends_on=[sps], reg_result="failed", reg_week=1,
                      reg_note="goods receipt posting error in regression",
                      expect=("Moved out", "MRC-06", "Regression failure, week 1"))
        self.add(R, "Order Management", "Project deployment: returns portal (Phoenix)",
                 "2026-10-01T10:30", work_type="Project deployment", risk="High",
                 duration=90, depends_on=[tr], user="pending",
                 expect=("Moved out", "DEP-01", "Its dependency failed regression"))
        self.add(R, "SAP HANA Platform", "System cleaning: HANA housekeeping and "
                 "log archive cleanup", "2026-09-22T09:00", work_type="System cleaning",
                 risk="Moderate", priority="High", downtime=330, comms_at=comms,
                 expect=(*ok, "System cleaning, 5.5h downtime"))
        self.add(R, "SAP HANA Platform", "SAP HANA database revision patch",
                 "2026-10-02T16:00", work_type="Downtime change", risk="Moderate",
                 priority="Medium", downtime=60, comms_at=comms,
                 expect=("Moved out", "MRC-04", "Does not fit the 6h window after cleaning"))
        ora = self.add(R, "Payments Gateway", "Oracle database quarterly patch",
                       "2026-09-28T12:00", system="ora-prd-db-01",
                       work_type="Downtime change", risk="High", downtime=90,
                       comms_at=comms, user="pending",
                       expect=("Moved out", "MRC-07", "Not approved by user at Go/No-Go"))
        self.add(R, "Pricing Engine", "Project deployment: dynamic pricing rules",
                 "2026-10-02T09:00", work_type="Project deployment", risk="Moderate",
                 duration=60, depends_on=[ora],
                 expect=("Moved out", "DEP-01", "Its dependency was not approved"))
        self.add(R, "Inventory API", "Project deployment: warehouse slotting",
                 "2026-10-05T14:00", work_type="Project deployment", risk="Moderate",
                 duration=75, a_result="failed", a_note="database migration timed out on A",
                 expect=("Moved out", "MRC-05", "A deployment failure"))
        self.add(R, "Customer Portal", "OS patching for application servers",
                 "2026-09-30T10:00", work_type="Downtime change", risk="Moderate",
                 downtime=45, comms_at=comms, expect=(*ok, "Downtime change"))
        self.add(R, "Reporting Warehouse", "Data warehouse storage expansion",
                 "2026-09-25T13:00", work_type="Downtime change", downtime=120,
                 comms_at=comms, expect=(*ok, "Downtime change"))
        kafka = self.add(R, "Notification Service", "Kafka cluster upgrade to v3.8",
                         "2026-09-23T10:00", system="kafka-prd-cluster",
                         work_type="Downtime change", risk="Moderate", downtime=60,
                         comms_at=comms, expect=(*ok, "Runs first; CRM change waits for it"))
        self.add(R, "CRM Integration", "Project deployment: CRM customer sync",
                 "2026-09-29T11:00", work_type="Project deployment", risk="Moderate",
                 duration=60, depends_on=[kafka],
                 expect=(*ok, "Healthy dependency: scheduled after the Kafka upgrade"))
        self.add(R, "Search Service", "Project deployment: new search index",
                 "2026-10-01T09:00", work_type="Project deployment", risk="Moderate",
                 downtime=40, comms_at=comms, expect=(*ok, "Project deployment"))
        self.add(R, "Auth Service", "Directory server upgrade", "2026-09-30T15:00",
                 work_type="Downtime change", risk="Moderate", downtime=60, comms_at=comms,
                 expect=(*ok, "Downtime change"))
        self.add(R, "HR Portal", "Enhancement: payroll export format", "2026-10-07T09:30",
                 work_type="Project deployment",
                 expect=("Moved out", "MRC-02", "Ready after D1"))
        self.add(R, "Mobile App Backend", "API gateway certificate rotation",
                 "2026-09-30T12:00", work_type="Downtime change", downtime=30,
                 comms_at=None,
                 expect=("Moved out", "DWN-02", "Downtime comms never sent"))

    # ------------------------------------------- ServiceNow field gates
    def demo_status_gates(self):
        self.add("WR-2026-1010", "Notification Service", "Enhancement: SMS delivery report",
                 "2026-10-07T11:00", status="New",
                 expect=("Moved out", "WRC-02", "Status still New at the cutoff"))
        self.add("WR-2026-1010", "Pricing Engine", "Enhancement: bulk price upload",
                 "2026-10-06T10:00", cab="pending",
                 expect=("Moved out", "WRC-02", "In progress but CAB approved = No"))
        self.add("MR-2026-10", "Auth Service", "Project deployment: MFA for admin users",
                 "2026-09-29T14:00", work_type="Project deployment", risk="Moderate",
                 duration=60, cab="pending",
                 expect=("Moved out", "MRC-02", "CAB approved = No at D1"))
        self.add("WR-2026-1010", "Search Service", "Enhancement: typo tolerance in search",
                 "2026-10-06T12:30", trs=False,
                 expect=("Moved out", "CHG-04", "No release note or TR list attached"))
        self.add("WR-2026-1010", "HR Portal", "Enhancement: holiday calendar export",
                 "2026-10-05T12:00", rfr=False,
                 expect=("Moved out", "WRC-05", "Approved to P = Yes but Status never set "
                                                "to Ready for release"))
        self.add("MR-2026-10", "SAP EWM Logistics", "SAP transport: pick list printout layout",
                 "2026-09-30T11:00", work_type="Project deployment", risk="Moderate",
                 duration=30, a_result="failed",
                 a_note="object locked by another transport in SAP-EWQ",
                 expect=("Moved out", "MRC-05", "Rev-Trac import RC 8 on Acceptance"))
        self.add("WR-2026-1010", "Payments Gateway", "Enhancement: saved cards list",
                 "2026-09-29T10:00", on_a_since="2026-09-29T16:25", moved_from="WR-2026-1003",
                 expect=("Deployed to P", None, "Carried over and already Deployed to A: "
                                                "not redeployed to A, still needs approval"))

    # ------------------------------------------------- filler releases
    def filler_weekly(self, saturday, n=6, avoid=()):
        cal = weekly_calendar(saturday)
        apps = [a for a in APPLICATIONS if a[1] not in avoid and not a[1].startswith("SAP")]
        for app in self.rng.sample(apps, n):
            day = self.rng.choice(cal["intake_days"])
            t = datetime.combine(day, datetime.min.time()).replace(
                hour=self.rng.randint(9, 14), minute=self.rng.choice([0, 15, 30, 45]))
            feat = self.rng.choice(ENHANCEMENTS)
            self.add(weekly_id(saturday), app[1], f"Enhancement: {feat}", iso(t),
                     duration=self.rng.choice([20, 30, 40]),
                     risk=self.rng.choice(["Low", "Low", "Moderate"]))

    def filler_monthly(self, year, month, n=5):
        cal = monthly_calendar(year, month)
        apps = self.rng.sample([a for a in APPLICATIONS if not a[1].startswith("SAP")], n)
        for app in apps:
            t = cal["d1"] - timedelta(days=self.rng.randint(2, 12), hours=self.rng.randint(1, 8))
            work = self.rng.choice(["Downtime change", "Project deployment"])
            desc = self.rng.choice(["OS patching for application servers",
                                    "Database minor version upgrade",
                                    f"Project deployment: {self.rng.choice(ENHANCEMENTS)}"])
            self.add(f"MR-{year}-{month:02d}", app[1], desc, iso(t), work_type=work,
                     risk="Moderate", downtime=self.rng.choice([0, 30, 60]),
                     duration=self.rng.choice([45, 60, 90]),
                     comms_at=iso(cal["comms_deadline"] - timedelta(days=3)))

    # ------------------------------------------------ history & incidents
    def history(self, start, n=60):
        for i in range(n):
            app = self.rng.choice(APPLICATIONS)
            when = start - timedelta(days=self.rng.randint(7, 120), hours=self.rng.randint(0, 20))
            outcome = self.rng.choices(["Successful", "Successful with issues",
                                        "Failed - rolled back"], weights=[85, 10, 5])[0]
            cid = f"CR-{1100 + i * 7}"
            rec = {"change_id": cid, "application": app[1], "closed_at": iso(when),
                   "close_code": outcome, "short_description":
                   f"Enhancement: {self.rng.choice(ENHANCEMENTS)}"}
            if outcome != "Successful" or self.rng.random() < 0.1:
                self.incidents.append({
                    "incident_id": f"INC-{5000 + len(self.incidents) * 7}",
                    "application": app[1],
                    "priority": self.rng.choice(["P2", "P3", "P3", "P4"]),
                    "opened_at": iso(when + timedelta(hours=6)),
                    "short_description": f"{app[1]}: errors after deployment of {cid}",
                    "caused_by_change": cid if outcome != "Successful" else None,
                })
            yield rec


def build(seed):
    b = Builder(seed)
    past = list(b.history(datetime(2026, 10, 1)))
    b.filler_weekly(date(2026, 10, 3), avoid=("Payments Gateway", "Pricing Engine",
                                              "Order Management"))
    b.demo_weekly()
    b.demo_monthly()
    for sat in (date(2026, 10, 17), date(2026, 10, 24), date(2026, 10, 31)):
        b.filler_weekly(sat)
    b.filler_monthly(2026, 11)
    b.demo_status_gates()      # added last so earlier change IDs stay stable

    releases = []
    for rid, cal in [(weekly_id(s), weekly_calendar(s)) for s in
                     (date(2026, 10, 3), date(2026, 10, 10), date(2026, 10, 17),
                      date(2026, 10, 24), date(2026, 10, 31))] + \
                    [("MR-2026-10", monthly_calendar(2026, 10)),
                     ("MR-2026-11", monthly_calendar(2026, 11))]:
        rel = {k: (iso(v) if isinstance(v, datetime) else
                   v.isoformat() if isinstance(v, date) else
                   [d.isoformat() for d in v] if isinstance(v, list) else v)
               for k, v in cal.items()}
        rel["release_manager"] = RELEASE_MANAGERS[len(releases) % 3]
        rel["change_ids"] = [c["change_id"] for c in b.changes
                             if c["requested_release"] == rid]
        releases.append(rel)
    releases.sort(key=lambda r: r["p_start"])

    freezes = [
        {"id": "FRZ-01", "name": "Quarter-end financial close",
         "start": "2026-09-28T00:00", "end": "2026-10-03T12:00", "scope": "applications",
         "applications": ["Payments Gateway", "Pricing Engine", "Order Management",
                          "SAP S/4HANA Finance"],
         "reason": "Finance systems locked while the quarter's books are closed."},
        {"id": "FRZ-02", "name": "Mega Sale event", "start": "2026-11-13T00:00",
         "end": "2026-11-16T06:00", "scope": "tier", "tiers": [1],
         "reason": "Peak traffic event; all Tier 1 systems frozen."},
        {"id": "FRZ-03", "name": "Year-end freeze", "start": "2026-12-14T00:00",
         "end": "2027-01-05T00:00", "scope": "all",
         "reason": "Reduced staffing over the holidays; no normal changes."},
    ]
    apps = [{"id": a, "name": n, "tier": t, "owning_team": team, "systems": s}
            for a, n, t, team, s in APPLICATIONS]
    write_attachments(b.changes, releases, DATA_DIR)
    return {
        "applications.json": apps,
        "releases.json": releases,
        "change_requests.json": b.changes,
        "change_history.json": past,
        "incidents.json": b.incidents,
        "freeze_windows.json": freezes,
        "planted_scenarios.json": b.planted,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    DATA_DIR.mkdir(exist_ok=True)
    for name in DATA_DIR.glob("*.json"):
        name.unlink()
    shutil.rmtree(DATA_DIR / "attachments", ignore_errors=True)
    for name, payload in build(args.seed).items():
        (DATA_DIR / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"{name:26s} {len(payload):4d} records")
    print(f"Written to {DATA_DIR}")


if __name__ == "__main__":
    main()
