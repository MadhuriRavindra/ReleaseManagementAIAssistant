# Emergency Change Process

**Owner:** Release Management Office, Orbitra Retail

## EMG-01 When a change qualifies as Emergency

A change qualifies as Emergency only if it:

- restores a service that is down or severely degraded (linked to an open P1 or P2 incident), or
- closes a critical security vulnerability that is being actively exploited or has a vendor deadline.

Missing a planning deadline is **not** a reason to raise an Emergency change.

## EMG-05 Delivery route

Emergency fixes are delivered through the weekly release (see WRC-01) and follow its daily 15:00 cutoff. A fix that cannot wait for Saturday is handled as an out-of-cycle emergency deployment by the Release Manager on duty.

## EMG-02 ECAB approval

Emergency changes are approved by the Emergency CAB (ECAB): the Release Manager on duty, the owning team's lead and the on-call Incident Manager. At least two of the three must approve **before implementation starts**. Approval can be given by phone or chat but must be recorded on the change within 2 hours.

An Emergency change in the Implement state without recorded ECAB approval is a compliance breach and must be escalated to the Release Manager immediately.

## EMG-03 Minimum testing

Emergency changes may use reduced testing, but the change record must state what was tested and what was not. "No testing" is only acceptable for a P1 outage and must be reviewed afterwards.

## EMG-04 Post-implementation review

Every Emergency change gets a post-implementation review within 5 business days, covering whether it was a genuine emergency and whether it could have gone through the Normal process.
