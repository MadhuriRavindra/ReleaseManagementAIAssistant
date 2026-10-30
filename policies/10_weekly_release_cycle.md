# Weekly Release Cycle

**Owner:** Release Management Office, Orbitra Retail
**Release ID:** WR-YYYY-MMDD, named after the Saturday of the Production deployment

## WRC-01 Scope

The weekly release carries **enhancements and emergency fixes only**. A change that requires downtime, or that depends on another change, is not eligible and is redirected to the next monthly release whose D1 has not yet passed.

## WRC-02 Daily cutoff (Monday to Thursday)

Changes are taken into the Acceptance release Monday to Thursday at the **15:00 IST** cutoff. At the cutoff, a change is taken only if **CAB approved = Yes** and its **Status = In progress**. A change with Status New, or with CAB approved = No, is not taken.

A change that reaches In progress after 15:00 joins the next day's intake. A change that reaches In progress after **Thursday 15:00**, or is still not eligible at that point, moves to the next weekly release. Changes already In progress before Monday join Monday's intake.

## WRC-03 Acceptance deployment

At 15:00 the Release Manager merges the TR lists of the changes taken that day into one consolidated TR list and hands it to the deployment team (see TRH-03). The deployment team imports the TRs into the Acceptance (A) environment at **16:00 IST** and sets each change's Status to **Deployed to A**. A change whose A deployment fails keeps Status In progress and moves to the next weekly release, since it cannot complete regression testing this week.

## WRC-04 Friday: regression testing

There are **no A deployments on Friday**. Friday is reserved for regression testing of everything deployed to A that week. A change that fails regression is moved to the next weekly release.

## WRC-05 Friday: approvals

By **Friday 18:00 IST**, every change must have **Approved to P = Yes** (set by the business user after testing on Acceptance) and **Status = Ready for release**. A change that does not is moved to the next weekly release with the reason "Not approved by user". The Release Manager then hands the deployment team a segregated TR list containing only the approved changes (see TRH-04).

## WRC-06 Saturday: Production deployment

Approved changes are deployed to Production on **Saturday between 08:00 and 10:00 IST**. Changes on different systems run in parallel; changes on the same system run one after another. Every change must finish by 10:00.
