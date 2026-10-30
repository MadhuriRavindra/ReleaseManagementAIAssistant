# Approvals and the Change Advisory Board (CAB)

**Owner:** Release Management Office, Orbitra Retail

## CAB-01 Purpose

The CAB reviews Normal changes for risk, business impact and scheduling before they reach Production.

## CAB-02 Meeting schedule

CAB meets every Monday and Wednesday at 11:00 IST. Emergency changes are approved by the ECAB (see EMG-02).

## CAB-03 Fields that control the release

The release process reads three ServiceNow fields (see CHG-04):

1. **CAB approved = Yes** is required before a change can be taken into the Acceptance release. CAB sets it at its Monday or Wednesday meeting; ECAB sets it for emergency fixes.
2. **Status** must be **In progress** at the Acceptance cutoff. The deployment team sets **Deployed to A** after deploying, and the change owner sets **Ready for release** once the change is approved for Production.
3. **Approved to P = Yes** is set by the business user after testing on Acceptance.

The Production deadline is Friday 18:00 IST for the weekly release and the Go/No-Go meeting (Saturday 12:00 IST) for the monthly release.

## CAB-04 Missing approval

A change without Approved to P = Yes, or whose Status is not Ready for release, at the Production deadline is moved out of the release to the next release of the same type, with the reason **"Not approved by user"**. It is not deployed on the strength of an approval promised later.

## CAB-05 Rejected changes

A rejected change returns to the requester with the CAB's reasons. It may be resubmitted as a new change.
