# Risk Assessment and Testing

**Owner:** Release Management Office, Orbitra Retail

## RSK-01 Risk levels

Every change is rated Low, Moderate or High by the change owner and confirmed at CAB.

| Factor | Low | Moderate | High |
|---|---|---|---|
| Application tier | Tier 3 | Tier 2 | Tier 1 |
| Type of work | Config tweak, patch | Feature release, minor upgrade | Schema migration, major upgrade, infrastructure move |
| Customer impact if it fails | None visible | Degraded service | Outage or data loss |
| Backout | Simple, under 15 min | Tested, under 1 hour | Complex or over 1 hour |

When factors disagree, the highest applicable level wins.

## RSK-02 Test evidence

Test evidence is **mandatory** for Moderate and High risk changes. Acceptable evidence is a link to passing test results from a pre-production environment, covering the changed functionality and a regression suite. A change without test evidence is not ready for implementation.

## RSK-03 Change history

When assessing risk, reviewers must consider the application's recent history. If an application has had **three or more incidents caused by changes in the last 60 days**, any new High-risk change on that application requires additional review by the Release Manager, and the implementation team should have the owning team's senior engineer on the call.

## RSK-04 Re-assessment

If scope, timing or dependencies change after CAB approval, the risk must be re-assessed and the change re-approved.
