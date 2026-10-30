# Change Freeze Policy

**Owner:** Release Management Office, Orbitra Retail

## FRZ-P01 What a freeze means

During a change freeze, no Normal or Standard changes may be implemented on the systems in scope. The current freeze calendar is published by the Release Management Office and is the source of truth for dates and scope.

## FRZ-P02 Freeze scope types

A freeze can apply to:

- **specific applications**, for example finance systems during quarter-end close
- **a tier**, for example all Tier 1 customer-facing systems during a peak sales event
- **all systems**, for example the year-end freeze

A change is in violation if any part of its planned window overlaps a freeze that covers its application.

## FRZ-P03 Freeze exceptions

A change may proceed during a freeze only with an approved **freeze exception**, recorded on the change. Exceptions require:

1. a business justification explaining why the change cannot wait
2. approval from the Release Manager and the owning application's business owner
3. a tested backout plan, regardless of risk level

Emergency fixes to restore service are allowed during a freeze, but still require ECAB approval.

## FRZ-P04 Standing freezes

- **Quarter-end close:** Payments Gateway, Pricing Engine, Order Management and SAP S/4HANA Finance, for the last days of each quarter.
- **Peak sales events:** all Tier 1 applications.
- **Year-end:** all systems, from mid-December until early January. There is no monthly release in December.

A weekly release change whose Production window falls in a freeze covering its application moves to the first weekly release after the freeze.
