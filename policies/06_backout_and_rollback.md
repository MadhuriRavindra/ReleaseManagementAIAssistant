# Backout and Rollback Policy

**Owner:** Release Management Office, Orbitra Retail

## BCK-01 Backout plan required

A documented backout plan is **mandatory for Moderate and High risk changes**, and for any change implemented under a freeze exception. A High-risk change without a backout plan must not be approved or implemented.

## BCK-02 What a backout plan must contain

- the exact steps to return to the previous working state
- the expected time to complete the backout
- the decision point: by what time, or on what signal, the team will decide to back out
- who makes the backout decision

## BCK-03 Database changes

Schema migrations must include a tested reverse migration, or a documented restore procedure from a backup taken immediately before the change.

## BCK-04 Executing a rollback

If post-implementation checks fail and cannot be fixed within the window, the team must back out rather than extend the window. Any rollback must be recorded on the change with close code "Failed - rolled back", and an incident raised if customers were affected.
