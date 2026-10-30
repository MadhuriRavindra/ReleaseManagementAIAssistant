# Dependencies and Downtime

**Owner:** Release Management Office, Orbitra Retail

## DEP-01 Moved-out dependencies

Dependencies are read from the TR lists (see TRH-02). If a change is moved out of a release at any stage, **every change in that release that depends on it, directly or through a chain, is moved out too**, to the same target release.

Example: if CR-A fails regression and a TR of CR-B must be imported after a TR of CR-A, then CR-B is moved out as well, and so is any CR-C that depends on CR-B.

## DEP-02 Order of implementation

In the cutover plan, a dependent change starts only after every change it depends on has finished.

## DEP-03 Impact of a delay

When a change is delayed, the Release Manager must identify every change that depends on it, directly or indirectly, and inform their owners before the next CAB.

## DEP-04 Dependencies and the weekly release

Changes with dependencies are never deployed through the weekly release (see WRC-01).

## DWN-01 Downtime changes

Changes that cause downtime go through the monthly release only (see WRC-01, MRC-01). The downtime duration must be recorded on the change.

## DWN-02 Downtime communication

Users must be informed of planned downtime **at least 48 hours before** the Production window starts, which for the monthly release means by Friday 00:00 IST. A downtime change without confirmed communication is moved out at Go/No-Go.
