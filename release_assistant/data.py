"""Load the synthetic release data and policy documents."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
POLICY_DIR = ROOT / "policies"


def parse(ts):
    return datetime.fromisoformat(ts) if ts else None


@dataclass
class ReleaseData:
    applications: list
    releases: list
    changes: list
    history: list
    incidents: list
    freezes: list
    policies: dict = field(default_factory=dict)   # rule_id -> {title, text, source}

    def __post_init__(self):
        self.by_id = {c["change_id"]: c for c in self.changes}
        self.release_by_id = {r["release_id"]: r for r in self.releases}
        # Dependencies are not a field on the ticket: like a release manager, we read them
        # from the TR list (a TR that must be imported after another change's TR).
        self.tr_owner = {t["tr_id"]: c["change_id"] for c in self.changes for t in c["tr_list"]}
        for c in self.changes:
            deps = [self.tr_owner.get(t["depends_on_tr"]) for t in c["tr_list"]
                    if t.get("depends_on_tr")]
            c["depends_on"] = sorted({d for d in deps if d and d != c["change_id"]})

    def change(self, change_id):
        cid = normalise_id(change_id)
        if cid not in self.by_id:
            raise KeyError(f"Unknown change {change_id}")
        return self.by_id[cid]


def normalise_id(text):
    """Accept 'cr2031', 'CR 2031', '2031' -> 'CR-2031'."""
    m = re.search(r"(\d{3,5})", str(text))
    return f"CR-{m.group(1)}" if m else str(text).strip().upper()


def load_policies():
    """Split each policy markdown file into sections keyed by rule ID (e.g. WRC-02)."""
    rules = {}
    for path in sorted(POLICY_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        doc_title = text.splitlines()[0].lstrip("# ").strip()
        for part in re.split(r"^## ", text, flags=re.M)[1:]:
            heading, _, body = part.partition("\n")
            m = re.match(r"([A-Z]+(?:-[A-Z]+)?-\d+)\s+(.*)", heading.strip())
            if m:
                rules[m.group(1)] = {"title": m.group(2), "text": body.strip(),
                                     "source": f"{doc_title} ({path.name})"}
    return rules


def load(data_dir=DATA_DIR):
    def read(name):
        return json.loads((Path(data_dir) / name).read_text(encoding="utf-8"))

    return ReleaseData(
        applications=read("applications.json"),
        releases=read("releases.json"),
        changes=read("change_requests.json"),
        history=read("change_history.json"),
        incidents=read("incidents.json"),
        freezes=read("freeze_windows.json"),
        policies=load_policies(),
    )
