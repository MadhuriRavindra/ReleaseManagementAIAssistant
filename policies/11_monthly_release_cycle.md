# Monthly Release Cycle

**Owner:** Release Management Office, Orbitra Retail
**Release ID:** MR-YYYY-MM; Production deployment on the last Sunday of the month

## MRC-01 Scope

The monthly release carries downtime changes, **system cleaning activities** (performed by the System Cleaning Team, typically 5 to 5.5 hours of downtime), project deployments and changes with dependencies. Changes that only need the weekly route may also be included.

## MRC-02 D1: ready in ServiceNow

By **D1, the Tuesday before extraction, 23:59 IST**, every change must have **CAB approved = Yes** and **Status = In progress** in ServiceNow, with its implementation and backout plans attached (see CHG-04). A change that does not meet this by D1 moves to the next monthly release.

## MRC-03 Extraction

On the **Wednesday after D1**, the changes are downloaded from ServiceNow and the release scope is frozen. No changes are added after extraction.

## MRC-04 Window capacity

The Production window is 6 hours. Changes on the same system run one after another, so the total duration planned on any one system must fit within 6 hours. When it does not, changes are kept in priority order (Critical, High, Medium, Low, then earliest ready), and the change that does not fit moves to the next monthly release.

## MRC-05 Acceptance deployment

On the **Monday after extraction**, the Release Manager merges the TR lists of all scoped changes into one consolidated TR list in dependency order (see TRH-03), and the deployment team deploys the release to Acceptance (A), setting each change's Status to **Deployed to A**. A change whose A deployment fails is moved to the next monthly release.

## MRC-06 Regression testing

After the A deployment there are **two weeks of regression testing**. A change that fails regression is moved to the next monthly release.

## MRC-07 Go/No-Go

On the **Saturday before the Production window (12:00 IST)** the Release Manager holds Go/No-Go. Every change needs **Approved to P = Yes** and **Status = Ready for release**, and, if it causes downtime, confirmed downtime communication (see DWN-02). A change that does not meet this is moved out with the reason "Not approved by user". The Release Manager then hands over the segregated TR list for Production (see TRH-04).

## MRC-08 Production deployment (cutover)

Production deployment runs on **Sunday 00:00 to 06:00 IST** as a downtime window. The cutover plan sequences the changes: one change at a time per system, and a dependent change starts only after the change it depends on has finished.
