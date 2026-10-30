# Change Types and Readiness

**Owner:** Release Management Office, Orbitra Retail
**Applies to:** all production changes

## CHG-01 Change types

| Type | When to use | Approval |
|---|---|---|
| Standard | Pre-approved, low-risk, repeatable change from the Standard Change Catalogue | Catalogue entry and user approval |
| Normal | Any planned change that is not Standard | CAB, technical and user approval |
| Emergency | Fix needed to restore service or close a critical security exposure | ECAB, technical and user approval |

## CHG-02 Release routes

Every change is delivered through one of two release cycles:

- the **weekly release** for enhancements and emergency fixes with no downtime and no dependencies (see the Weekly Release Cycle policy)
- the **monthly release** for downtime changes, system cleaning activities, project deployments and changes with dependencies (see the Monthly Release Cycle policy)

## CHG-03 Work types

Each change records its work type: Enhancement, Emergency fix, Downtime change, System cleaning or Project deployment. The work type decides the release route.

## CHG-04 Ready in ServiceNow

The ServiceNow ticket carries the fields and attachments that decide whether a change can be released:

- **CAB approved** (Yes / No), set when the CAB (or ECAB for emergencies) approves the change
- **Approved to P** (Yes / No), set by the business user after testing on Acceptance
- **Status**: New → In progress → Deployed to A → Ready for release → Deployed to P → Closed
- attachments: a **release note** and a **TR list** (see TRH-01)

A change is ready for the **Acceptance release** when CAB approved = Yes, Status = In progress, the release note and TR list are attached, and it has an implementation plan (and a backout plan for Moderate and High risk).

A change is ready for the **Production release** when Approved to P = Yes and its Status is Ready for release.

## CHG-05 Moving a change out of a release

When a change is moved out of a release, the change record states the stage, the reason and the release it moves to. The change owner is informed the same day.
