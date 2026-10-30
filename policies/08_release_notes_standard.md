# Release Notes Standard

**Owner:** Release Management Office, Orbitra Retail

## RN-01 When release notes are needed

Release notes are published for every release window that contains at least one Normal change to a Tier 1 or Tier 2 application.

## RN-02 Structure

Release notes are grouped by application and contain:

- **Summary:** one or two sentences on what is changing and why
- **Changes included:** change number, short description, risk level
- **New features and fixes:** written for business readers, not engineers
- **Known issues and limitations**
- **Contacts:** owning team for each application

## RN-03 Writing style

- Write for a non-technical reader. "Customers can now track orders in real time" instead of "added websocket endpoint for order events".
- Do not include commit hashes, internal ticket numbers other than change numbers, or people's names.
- Only describe changes that were deployed to Production. Changes moved out of the release are listed separately under "Moved to a later release".
