"""
Deployment tool connectors.

The release console hands a TR list to a deployment tool and waits for its confirmation.
SAP transports go to Rev-Trac; other applications' packages go to a CI/CD pipeline.

Both connectors here are SIMULATED: they return the results a real tool would report,
using the scenario data (a change marked as failing on A fails its import). To connect
the real tools, implement `DeploymentTool.submit` against their APIs; nothing else in
the console has to change.

SAP transport return codes (RC): 0 = imported, 4 = imported with warnings,
8 = import errors, 12 or higher = import cancelled. RC 0 and 4 count as deployed.
"""

import zlib
from datetime import timedelta

SUCCESS_MAX_RC = 4


def is_sap_tr(row):
    return str(row["Target"]).startswith("SAP-")


class DeploymentTool:
    name = "Deployment tool"
    job_prefix = "JOB"

    def __init__(self):
        self._seq = 0

    def next_job_id(self, env, when):
        self._seq += 1
        return f"{self.job_prefix}-{env}-{when:%y%m%d}-{self._seq:03d}"

    def submit(self, rows, env, start, failing, timing=None):
        """Import `rows` (TR list rows, already in dependency order) into `env`.

        `failing` maps change_id -> failure note for changes whose deployment fails.
        `timing` optionally maps change_id -> (start, end) from the cutover plan.
        Returns a job: {job_id, tool, env, submitted_at, finished_at, results: [...]}.
        Each result: {TR, Change, RC, Result, Message, Started, Finished}.
        """
        raise NotImplementedError


class _Simulated(DeploymentTool):
    minutes_per_tr = 5

    def rc_for(self, row, failing, failed_changes):
        raise NotImplementedError

    def submit(self, rows, env, start, failing, timing=None):
        t = start
        results, failed_changes = [], set()
        per_change = {}
        for row in rows:
            per_change[row["Change"]] = per_change.get(row["Change"], 0) + 1
        done = {}
        for row in rows:
            cid = row["Change"]
            if cid in failed_changes:          # later TRs of a failed change are skipped
                results.append({"TR": row["TR"], "Change": cid, "RC": None,
                                "Result": "Skipped", "Message": "Earlier TR of this change "
                                "failed", "Started": None, "Finished": None})
                continue
            rc, msg = self.rc_for(row, failing, failed_changes)
            if timing and cid in timing:        # follow the cutover plan's slot
                s0, e0 = timing[cid]
                step = (e0 - s0) / per_change[cid]
                i = done.get(cid, 0)
                started, finished = s0 + step * i, s0 + step * (i + 1)
                done[cid] = i + 1
                t = max(t, finished)
            else:
                started, t = t, t + timedelta(minutes=self.minutes_per_tr)
                finished = t
            ok = rc is not None and rc <= SUCCESS_MAX_RC
            if not ok:
                failed_changes.add(cid)
            results.append({"TR": row["TR"], "Change": cid, "RC": rc,
                            "Result": "Imported" if rc == 0 else
                                      "Imported with warnings" if ok else "Failed",
                            "Message": msg, "Started": started, "Finished": finished})
        return {"job_id": self.next_job_id(env, start), "tool": self.name, "env": env,
                "submitted_at": start, "finished_at": t, "results": results}


class RevTracSimulator(_Simulated):
    """Simulated Rev-Trac: imports SAP transports and reports SAP return codes."""
    name = "Rev-Trac"
    job_prefix = "RT"
    minutes_per_tr = 6

    def rc_for(self, row, failing, failed_changes):
        cid = row["Change"]
        if cid in failing:
            return 8, f"Import error: {failing[cid]}"
        if zlib.crc32(row["TR"].encode()) % 5 == 0:
            return 4, "Imported with warnings (generation warnings, reviewed)"
        return 0, "Imported successfully"


class PipelineSimulator(_Simulated):
    """Simulated CI/CD pipeline for non-SAP application and configuration packages."""
    name = "CI/CD pipeline"
    job_prefix = "PL"
    minutes_per_tr = 4

    def rc_for(self, row, failing, failed_changes):
        cid = row["Change"]
        if cid in failing:
            return 8, f"Pipeline stage failed: {failing[cid]}"
        return 0, "Deployed, smoke tests passed"


class DeploymentHub:
    """Routes each TR to the right tool and collects the jobs."""

    def __init__(self):
        self.revtrac = RevTracSimulator()
        self.pipeline = PipelineSimulator()

    def deploy(self, rows, env, start, failing, timing=None):
        jobs = []
        sap = [r for r in rows if is_sap_tr(r)]
        other = [r for r in rows if not is_sap_tr(r)]
        pipeline_start = start
        if sap:
            job = self.revtrac.submit(sap, env, start, failing, timing)
            jobs.append(job)
            sap_trs = {r["TR"] for r in sap}
            if any(r["Import after"] in sap_trs for r in other):
                pipeline_start = job["finished_at"]   # wait for the SAP TRs it depends on
        if other:
            jobs.append(self.pipeline.submit(other, env, pipeline_start, failing, timing))
        return jobs
