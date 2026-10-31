"""
Grounded Q&A over the release cycle results, using Groq.

The LLM never decides whether a change goes to Production. It receives the
cycle engine's results, the relevant change records and the policy text, and
explains them.
"""

import json
import os
import re

from .cycles import ReleaseCycle, delay_impact, upstream_chain
from .data import normalise_id

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
# Tried in this order when a model is not available to the API key
PREFERRED_MODELS = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b",
                    "qwen/qwen3.8-27b", "llama-3.1-8b-instant"]
NOT_CHAT = ("whisper", "guard", "orpheus", "tts", "safeguard")

SYSTEM_PROMPT = """You are an AI Release Management Assistant for Orbitra Retail.

Orbitra runs two release cycles:
- Weekly (WR-...): enhancements and emergency fixes, no downtime, no dependencies.
  Mon-Thu intake with 15:00 IST cutoff and A deployment at 16:00; Friday regression and
  approvals (deadline 18:00); Production Saturday 08:00-10:00 IST.
- Monthly (MR-...): downtime changes, system cleaning, project deployments, dependent
  changes. D1 (Tuesday) ready in ServiceNow; Wednesday extraction; Monday A deployment;
  2 weeks regression; Go/No-Go Saturday 12:00; Production Sunday 00:00-06:00 IST.

Each ServiceNow ticket carries: CAB approved (Yes/No), Approved to P (Yes/No), a Status
(New -> In progress -> Deployed to A -> Ready for release -> Deployed to P -> Closed), and
two attachments: a release note and a TR (transport request) list. Dependencies between
changes come from the TR lists (a TR that must be imported after another change's TR).
- Acceptance release: CAB approved = Yes and Status = In progress at the cutoff
  (weekly 15:00, monthly D1), with release note and TR list attached. The release manager
  merges the TRs of all scoped changes into one consolidated TR list for the deployment team.
- TR lists are sent to Rev-Trac (SAP transports) and the CI/CD pipeline (other packages).
  When the tool confirms every TR of a change (SAP RC 0 or 4), Status is set to Deployed to A /
  Deployed to P automatically; RC 8 or higher means the deployment failed.
- Production release: Approved to P = Yes and Status = Ready for release by the deadline
  (weekly Friday 18:00, monthly Go/No-Go); otherwise "Not approved by user". The release
  manager hands over a segregated TR list with only the approved changes, plus a
  do-not-deploy list.

Answer ONLY from the CONTEXT. Rules:
- Outcomes (deployed / moved out, and why) come from a deterministic release engine.
  Never change or invent an outcome; explain it.
- Always cite change IDs (e.g. CR-2031), release IDs and policy rule IDs (e.g. WRC-05).
  Cite a policy rule ID only if it appears in the CONTEXT.
- If the CONTEXT has a "note" saying no change or release ID was named, and the question is
  about a specific change, approval or sign-off, ask which change or release ID they mean.
  Do not answer from the default releases.
- If the context does not contain the answer, say so plainly.
- Be concise and practical, like an experienced release manager briefing CAB."""


def find_targets(question, data):
    q = question.upper()
    release_ids = [r for r in re.findall(r"(?:WR-\d{4}-\d{4}|MR-\d{4}-\d{2})", q)
                   if r in data.release_by_id]
    change_ids = [normalise_id(m) for m in re.findall(r"CR[-\s]?\d{3,5}", q)]
    change_ids = [c for c in change_ids if c in data.by_id]
    for c in change_ids:
        release_ids.append(data.by_id[c]["requested_release"])
    ql = question.lower()
    if "week" in ql and not any(r.startswith("WR") for r in release_ids):
        release_ids.append("WR-2026-1010")
    if "month" in ql and not any(r.startswith("MR") for r in release_ids):
        release_ids.append("MR-2026-10")
    if not release_ids:
        release_ids = ["WR-2026-1010", "MR-2026-10"]
    return list(dict.fromkeys(release_ids)), change_ids


CONTEXT_BUDGET_CHARS = 9000        # about 3,000 tokens: fits Groq's free-tier limits
PLAN_WORDS = ("cutover", "plan", "window", "schedule", "sequence", "order", "production",
              "deploy", "rev-trac", "revtrac", "pipeline", "tr list", "transport")


def _short(text, n=120):
    text = str(text)
    return text if len(text) <= n else text[:n - 1] + "…"


def _release_facts(data, cy, question):
    ql = question.lower()
    cal = cy.cal
    if cal["type"] == "Weekly":
        dates = (f"intake Mon-Thu cutoff 15:00, A 16:00; Fri approvals till 18:00; "
                 f"P {cal['p_start']:%a %d %b %H:%M}-{cal['p_end']:%H:%M}")
    else:
        dates = (f"D1 {cal['d1']:%a %d %b}; extraction {cal['extraction']:%a %d %b}; "
                 f"A {cal['a_deploy']:%a %d %b}; Go/No-Go {cal['go_no_go']:%a %d %b %H:%M}; "
                 f"P {cal['p_start']:%a %d %b %H:%M}-{cal['p_end']:%H:%M}")
    facts = {
        "name": cal["name"], "dates": dates, "requested": len(cy.changes),
        "deployed_to_P": sorted(cid for cid, st in cy.status.items() if st == "Deployed to P"),
        "moved_out": [f"{cid} ({data.by_id[cid]['application']}) at {m['stage']}: "
                      f"{_short(m['reason'])} [{m['rule']}] -> {m['target']}"
                      for cid, m in cy.moved.items()],
        "tr_lists": [f"{h['title']}: {len(h['rows'])} TRs from {len(h['changes'])} changes"
                     + (f"; do-not-deploy {sorted({x['Change'] for x in h['excluded']})}"
                        if h["excluded"] else "") for h in cy.handovers.values()],
        "tool_failures": [f"{j['tool']} {j['job_id']}: {r['TR']} RC {r['RC']} ({r['Change']})"
                          for js in cy.jobs.values() for j in js for r in j["results"]
                          if r["Result"] == "Failed"],
    }
    if any(w in ql for w in PLAN_WORDS):
        facts["production_plan"] = [
            f"{p['change_id']} {p['system']} {p['start']:%H:%M}-{p['end']:%H:%M}"
            + (f" after {','.join(p['depends_on'])}" if p["depends_on"] else "")
            for p in cy.deploy_plan]
    return facts


def _change_facts(data, cy, cid):
    c = data.by_id[cid]
    return {
        "change": f"{cid} {c['application']} ({c['system']}): {c['short_description']}; "
                  f"{c['work_type']}, {c['change_type']}, risk {c['risk']}, "
                  f"release {c['requested_release']}"
                  + (f", carried over from {c['moved_from_release']}"
                     if c.get("moved_from_release") else ""),
        "fields": f"CAB approved {c['cab_approved']} ({c['cab_approved_at']}); Approved to P "
                  f"{c['approved_to_p']} ({c['approved_to_p_at']}); downtime "
                  f"{c['downtime_minutes']} min",
        "status_history": [f"{h['status']} {h['at']} by {h['by']}"
                           for h in cy.status_history(cid)],
        "outcome": cy.status[cid],
        "moved_out": (f"at {cy.moved[cid]['stage']}: {cy.moved[cid]['reason']} "
                      f"[{cy.moved[cid]['rule']}] -> {cy.moved[cid]['target']}"
                      if cid in cy.moved else None),
        "trs": [t["tr_id"] + (f" (after {t['depends_on_tr']})" if t["depends_on_tr"] else "")
                for t in c["tr_list"]] or "no release note / TR list attached",
        "deployment_log": [f"{j['env']} {j['tool']}: {r['TR']} RC {r['RC']} {r['Result']}"
                           for js in cy.jobs.values() for j in js for r in j["results"]
                           if r["Change"] == cid],
        "depends_on_chain": upstream_chain(data, cid),
        "blocked_if_delayed": [i["change_id"] for i in delay_impact(data, cid)],
    }


def build_context(question, data, minimal=False):
    """Compact, targeted context: only what the question needs, within a size budget."""
    release_ids, change_ids = find_targets(question, data)
    cycles = {rid: ReleaseCycle(data, rid) for rid in release_ids}
    focus = {cid: _change_facts(data, cycles[data.by_id[cid]["requested_release"]], cid)
             for cid in change_ids}
    releases = {rid: _release_facts(data, cy, question) for rid, cy in cycles.items()}

    rules = []
    for cid in change_ids:
        cy = cycles[data.by_id[cid]["requested_release"]]
        if cid in cy.moved:
            rules.append(cy.moved[cid]["rule"])
    for kw, rid in [("rev", "TRH-05"), ("rc ", "TRH-05"), ("transport", "TRH-03"),
                    ("tr list", "TRH-03"), ("cutoff", "WRC-02"), ("approv", "CAB-04"),
                    ("regression", "WRC-04"), ("downtime", "DWN-02"), ("depend", "DEP-01"),
                    ("d1", "MRC-02"), ("capacity", "MRC-04"), ("window", "MRC-04"),
                    ("clean", "MRC-01"), ("emergency", "EMG-05"), ("go/no-go", "MRC-07"),
                    ("freeze", "FRZ-P02")]:
        if kw in question.lower():
            rules.append(rid)
    if not change_ids:
        for cy in cycles.values():
            rules += [m["rule"] for m in cy.moved.values()]
    rules = [r for r in dict.fromkeys(rules) if r in data.policies][:5]
    policy = {r: _short(data.policies[r]["text"], 350) for r in rules}

    overview = [f"{r['release_id']}: P {r['p_start'][:16]}, {len(r['change_ids'])} requested"
                for r in data.releases]
    context = {"releases_in_question": releases, "changes_in_question": focus,
               "policy_rules": policy, "all_releases": overview}

    # Tell the model when the releases above are only defaults, not what the user named
    named = (re.search(r"(?:WR-\d{4}-\d{4}|MR-\d{4}-\d{2}|CR[-\s]?\d{3,5})", question.upper())
             or "week" in question.lower() or "month" in question.lower())
    if not named:
        context["note"] = ("No change or release ID was named in the question; the releases "
                           "below are demo defaults, not what the user asked about.")

    def dump():
        return json.dumps(context, separators=(",", ":"), default=str, ensure_ascii=False)

    # stay within budget: drop the least important parts first
    for drop in (["all_releases"] if not minimal else ["all_releases", "policy_rules"]):
        if minimal or len(dump()) > CONTEXT_BUDGET_CHARS:
            context.pop(drop, None)
    if len(dump()) > CONTEXT_BUDGET_CHARS or minimal:
        for f in releases.values():
            f.pop("production_plan", None) if focus else None
            f["moved_out"] = f["moved_out"][:12]
    if len(dump()) > CONTEXT_BUDGET_CHARS:
        context.pop("policy_rules", None)
    sources = release_ids + change_ids + rules
    return dump(), sources


def available_models(api_key):
    """Chat models this API key can use, best first."""
    from groq import Groq
    ids = [m.id for m in Groq(api_key=api_key).models.list().data
           if not any(x in m.id for x in NOT_CHAT)]
    ranked = [m for m in PREFERRED_MODELS if m in ids]
    return ranked + sorted(m for m in ids if m not in ranked)


def _is_too_large(err):
    code = getattr(err, "status_code", None)
    return code == 413 or "too large" in str(err).lower() or "tokens per minute" in str(err)


def _unsupported_citations(reply, context):
    """Policy rule IDs cited in the reply that do not appear in the context sent to the model."""
    normal = reply.replace("\u2011", "-").replace("\u2010", "-").replace("\u2013", "-")
    cited = set(re.findall(r"\b[A-Z]{3}-\d{2}[A-Z]?\b", normal))
    return sorted(c for c in cited if c not in context)


def answer(question, data, api_key, model=None, history=None):
    """Returns (reply, sources, model_used). Falls back to another model if the chosen one
    is not available to this key, and retries with a smaller context if the request is
    too large for the key's token limits."""
    from groq import APIStatusError, Groq, NotFoundError  # dashboard works without groq

    client = Groq(api_key=api_key)
    recent = [{"role": m["role"], "content": _short(m["content"], 500)}
              for m in (history or [])[-2:]]

    def ask(m, minimal):
        context, sources = build_context(question, data, minimal=minimal)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + recent + [
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"}]
        resp = client.chat.completions.create(model=m, messages=messages, temperature=0.1,
                                              max_tokens=700)
        reply = resp.choices[0].message.content
        unsupported = _unsupported_citations(reply, context)
        if unsupported:
            reply += (f"\n\n_Check: {', '.join(unsupported)} is cited above but is not in the "
                      "retrieved context._")
        return reply, sources

    tried, candidates = [], [model or DEFAULT_MODEL]
    while candidates:
        m = candidates.pop(0)
        tried.append(m)
        try:
            try:
                reply, sources = ask(m, minimal=False)
            except APIStatusError as e:
                if not _is_too_large(e):
                    raise
                recent.clear()                        # retry once, smaller
                reply, sources = ask(m, minimal=True)
            return reply, sources, m
        except NotFoundError:
            if len(tried) == 1:
                candidates = [x for x in available_models(api_key) if x not in tried]
            if not candidates:
                raise RuntimeError("None of the Groq models are available to this API key "
                                   f"(tried: {', '.join(tried)}). Check the model "
                                   "permissions for your project in the Groq console.")
        except APIStatusError as e:
            if _is_too_large(e):
                raise RuntimeError("The question is still too large for your Groq plan's "
                                   "token limit. Wait a minute (the limit is per minute) and "
                                   "ask about one change or one release at a time.") from e
            raise