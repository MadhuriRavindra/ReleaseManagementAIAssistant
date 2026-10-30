# Release Notes, TR Lists and Deployment Handover

**Owner:** Release Management Office, Orbitra Retail

## TRH-01 Attachments on every change

Every change must have two attachments in ServiceNow before it can be taken into a release: a **release note** (what changes, deployment steps, dependencies, downtime, rollback) and a **TR list** (the transport requests to import, in sequence, with their Acceptance and Production targets). A change without them is not taken (see CHG-04).

## TRH-02 Dependencies come from the TR list

Dependencies between changes are declared in the TR list and the release note: a TR that must be imported after a TR belonging to another change makes the first change dependent on the second. The Release Manager uses these to order the deployment and to apply DEP-01.

## TRH-03 Consolidated TR list for Acceptance

For every Acceptance deployment (weekly Monday to Thursday at 16:00, monthly on the A deployment Monday), the Release Manager takes the list of scoped changes from ServiceNow, merges the TR lists of all of them into **one consolidated TR list** in dependency order, and hands it to the deployment team.

## TRH-04 Segregated TR list for Production

Before the Production window (weekly on Friday after the approval deadline, monthly after Go/No-Go), the Release Manager prepares a **segregated TR list**: only the TRs of changes with Approved to P = Yes and Status = Ready for release, in dependency order. TRs of changes that were on Acceptance but are not approved are listed separately as **do not deploy**.

## TRH-05 Deployment through Rev-Trac and the CI/CD pipeline

The Release Manager hands each TR list to the deployment tools: **SAP transports go to Rev-Trac**, other application and configuration packages go to the **CI/CD pipeline**. Non-SAP packages that must be imported after an SAP transport wait until Rev-Trac has finished.

The tools confirm every TR with a result. For SAP transports the return code (RC) decides: **RC 0** imported, **RC 4** imported with warnings, **RC 8** import errors, **RC 12 or higher** import cancelled. When every TR of a change is confirmed with RC 0 or 4, the change Status is set **automatically** to **Deployed to A** or **Deployed to P** through the integration; the release console reads that Status to show where each change is.

If any TR of a change fails (RC 8 or higher), its remaining TRs are skipped, the Status stays In progress, and the change is moved out of the release (see WRC-03, MRC-05).
