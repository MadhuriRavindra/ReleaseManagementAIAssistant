"""
Tests for the release cycle engine.

Run from the project folder:  python -m pytest -q
"""

import json
from pathlib import Path

import pytest

from release_assistant.cycles import DEPLOYED, MOVED, ReleaseCycle, delay_impact
from release_assistant.data import load, normalise_id

ROOT = Path(__file__).resolve().parent.parent
PLANTED = json.loads((ROOT / "data" / "planted_scenarios.json").read_text())
DATA = load()
CYCLES = {r["release_id"]: ReleaseCycle(DATA, r["release_id"]) for r in DATA.releases}


@pytest.mark.parametrize("case", PLANTED, ids=[p["change_id"] for p in PLANTED])
def test_scripted_outcome(case):
    cycle = CYCLES[case["release"]]
    status = cycle.status[case["change_id"]]
    if case["expected_outcome"] == "Moved out":
        assert status == MOVED
        assert cycle.moved[case["change_id"]]["rule"] == case["expected_rule"]
    else:
        assert status == DEPLOYED


def test_filler_releases_deploy_everything():
    demo = {"WR-2026-1010", "MR-2026-10"}
    for rid, cycle in CYCLES.items():
        if rid not in demo:
            assert not cycle.moved, f"{rid} unexpectedly moved {list(cycle.moved)}"


def test_weekly_never_deploys_downtime_or_dependent_changes():
    for rid, cycle in CYCLES.items():
        if rid.startswith("WR"):
            for cid in cycle.summary()["deployed"]:
                c = DATA.by_id[cid]
                assert not c["downtime_required"] and not c["depends_on"]


def test_weekly_moves_go_to_next_week_or_monthly():
    cycle = CYCLES["WR-2026-1010"]
    for m in cycle.moved.values():
        assert m["target"] in ("WR-2026-1017", "MR-2026-11")


@pytest.mark.parametrize("rid", [r for r in CYCLES if r.startswith("MR")])
def test_cutover_plan_is_valid(rid):
    cycle = CYCLES[rid]
    plan = {p["change_id"]: p for p in cycle.deploy_plan}
    for p in plan.values():
        assert p["fits"], f"{p['change_id']} runs past the window"
        for dep in DATA.by_id[p["change_id"]]["depends_on"]:
            if dep in plan:
                assert p["start"] >= plan[dep]["end"]
    by_system = {}
    for p in plan.values():
        by_system.setdefault(p["system"], []).append(p)
    for items in by_system.values():
        items.sort(key=lambda p: p["start"])
        for a, b in zip(items, items[1:]):
            assert b["start"] >= a["end"], "two changes overlap on one system"


def test_moved_dependency_takes_its_dependents_with_it():
    cycle = CYCLES["MR-2026-10"]
    for cid, m in cycle.moved.items():
        if m["rule"] == "DEP-01":
            deps = DATA.by_id[cid]["depends_on"]
            assert any(d in cycle.moved for d in deps)


def test_delay_impact_follows_chain():
    root = next(c for c in DATA.changes if c["requested_release"] == "MR-2026-10"
                and c["short_description"].startswith("SAP support package"))
    impacted = [i["change_id"] for i in delay_impact(DATA, root["change_id"])]
    assert len(impacted) == 2


def test_id_normalisation():
    assert normalise_id("cr2031") == "CR-2031"
    assert normalise_id("CR 2031") == "CR-2031"


def test_dependencies_come_from_tr_lists():
    raw = json.loads((ROOT / "data" / "change_requests.json").read_text())
    assert all("depends_on" not in c for c in raw), "dependencies must not be a stored field"
    for c in DATA.changes:
        for d in c["depends_on"]:
            parent_trs = {t["tr_id"] for t in DATA.by_id[d]["tr_list"]}
            assert any(t["depends_on_tr"] in parent_trs for t in c["tr_list"])


@pytest.mark.parametrize("rid", list(CYCLES))
def test_a_handover_lists_exactly_the_scoped_changes_trs(rid):
    cycle = CYCLES[rid]
    for key, h in cycle.handovers.items():
        if h["env"] != "A":
            continue
        expected = {t["tr_id"] for cid in h["changes"] for t in DATA.by_id[cid]["tr_list"]}
        assert {r["TR"] for r in h["rows"]} == expected
        order = [r["Change"] for r in h["rows"]]
        for cid in h["changes"]:            # dependencies are imported first
            for dep in DATA.by_id[cid]["depends_on"]:
                if dep in order:
                    assert order.index(dep) < order.index(cid)


@pytest.mark.parametrize("rid", list(CYCLES))
def test_p_handover_only_contains_deployed_changes(rid):
    cycle = CYCLES[rid]
    p = [h for h in cycle.handovers.values() if h["env"] == "P"]
    assert len(p) == 1
    handed = {r["Change"] for r in p[0]["rows"]}
    assert handed == set(cycle.summary()["deployed"])
    assert not handed & {x["Change"] for x in p[0]["excluded"]}


def test_board_follows_deployment_team_status():
    cycle = CYCLES["WR-2026-1010"]
    for cid in cycle.summary()["deployed"]:
        statuses = [h["status"] for h in cycle.status_history(cid)]
        assert statuses.index("Deployed to A") < statuses.index("Ready for release") \
            < statuses.index("Deployed to P") < statuses.index("Closed")


def test_change_already_on_a_is_not_redeployed_to_a():
    carried = [p["change_id"] for p in PLANTED if p["scenario"].startswith("Carried over")]
    assert carried
    for cid in carried:
        cycle = CYCLES[DATA.by_id[cid]["requested_release"]]
        a_lists = [h for h in cycle.handovers.values() if h["env"] == "A"]
        assert all(cid not in h["changes"] for h in a_lists)
        assert cycle.status[cid] == DEPLOYED          # still goes to P once approved
        a_updates = [u for u in cycle.sn_updates[cid] if u["status"] == "Deployed to A"]
        assert not a_updates, "deployment team must not deploy it to A again"


def test_every_change_with_trs_has_attachment_files():
    for c in DATA.changes:
        if c["tr_list"]:
            names = {a["kind"]: a for a in c["attachments"]}
            assert names["Release note"]["name"].endswith(".docx")
            assert names["TR list"]["name"].endswith(".xlsx")
            for a in c["attachments"]:
                assert (ROOT / "data" / a["path"]).exists()


@pytest.mark.parametrize("rid", list(CYCLES))
def test_status_updates_come_from_tool_confirmations(rid):
    cycle = CYCLES[rid]
    jobs = [j for js in cycle.jobs.values() for j in js]
    for cid in cycle.summary()["deployed"]:
        for env in ("A", "P"):
            upd = [u for u in cycle.sn_updates[cid] if u["status"] == f"Deployed to {env}"]
            if env == "A" and not upd:           # carried over: already on A
                continue
            assert upd and upd[0]["by"].endswith("integration")
            res = [r for j in jobs if j["env"] == env for r in j["results"]
                   if r["Change"] == cid]
            assert res and all(r["RC"] is not None and r["RC"] <= 4 for r in res)


def test_failed_imports_move_the_change_out():
    for cycle in CYCLES.values():
        for js in cycle.jobs.values():
            for j in js:
                for r in j["results"]:
                    if r["Result"] == "Failed":
                        assert r["RC"] >= 8
                        assert cycle.status[r["Change"]] == MOVED
                        assert r["TR"] in cycle.moved[r["Change"]]["reason"]


def test_revtrac_handles_sap_and_pipeline_the_rest():
    for cycle in CYCLES.values():
        for js in cycle.jobs.values():
            for j in js:
                sap = {r["TR"][3:5] == "K9" for r in j["results"]}
                assert sap == ({True} if j["tool"] == "Rev-Trac" else {False})
