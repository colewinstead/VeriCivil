# Paid-Pilot Operations Manual

Current free desktop releases target unsigned Windows x64 builds. Code signing work and Mac desktop builds are paused. This paid-pilot process does not describe the active public release channel; see [desktop readiness](desktop-production-readiness.md).

This manual defines the minimum operating process for a controlled pilot. It does not activate payment, create contractual service levels, or replace attorney-approved terms.

## Roles and records

Every pilot identifies these people in its private acceptance record:

- **Release owner:** approves the exact commit and artifacts, retains the prior release, and owns rollback.
- **Engineering acceptance owner:** confirms the private PE record and representative engineering acceptance cover the released versions and pilot scope.
- **Pilot operations owner:** maintains the user/seat register, onboarding, support queue, incident log, and offboarding.
- **Legal approval owner:** records the controlling counsel-approved agreements and acceptance method.

The private evidence location contains release identity, approvals, test output, hashes, signatures, screenshots, sanitized engineering acceptance, exceptions, and rollback evidence. It is access-controlled and is not synchronized into the public repository.

## Supported pilot scope

The pilot owner narrows these limits further for each recipient.

- Manual single circular curves using a displayed, versioned MDOT or TDOT profile.
- LandXML alignments composed of supported lines and circular arcs, with declared units and reviewable station equations.
- Project save/open using the current schema and explicitly tested compatibility fixtures.
- PDF, ORD CSV, and overlay DXF only after the applicable real-tool acceptance record is approved.
- Browser versions and desktop operating systems listed in the private release acceptance record.
- Spirals are not supported engineering geometry for the first pilot and must remain visibly blocked or warned; they are not silently approximated.
- Unrecognized or conflicting coordinate declarations require user review and are never silently selected.
- Users independently confirm governing-standard applicability, current revisions, design exceptions, classifications, units, curve direction, stationing, coordinates, and deliverables.

## Onboarding checklist

1. Confirm the named user, organization, assigned plan/seat, approved release, supported device/browser, and support contact.
2. Provide the approved license/pilot terms, privacy notice, supported-input limits, known limitations, local-storage explanation, backup instructions, and responsible-project-PE statement.
3. Obtain the attorney-approved acceptance or acknowledgment before granting a paid entitlement.
4. Install or open only the version-pinned approved release. For desktop, verify the artifact hash and signature before launch.
5. Complete the synthetic training calculation without customer data.
6. Demonstrate local project backup and recovery, entitlement outage behavior, diagnostic generation, support submission, and rollback instructions.
7. Record completion in the private user/seat register; do not record project names or engineering content in the entitlement ledger.

## Local data, privacy, and recovery

- Engineering files and calculations remain on the user's device. Authentication, billing, entitlement, and support systems do not receive them automatically.
- The service-side minimum data set is internal user ID, organization, named seat, plan, subscription/entitlement status, token issue/expiry, and audit timestamps.
- Do not collect project name, route, alignment, curve, station, coordinate, calculation, or export data as telemetry.
- Browser storage and locally saved projects are the customer's working copies. Users choose their own approved storage/backup location.
- Before a version change or entitlement recovery test, save a local recovery project copy.
- After grace expiry, existing inputs and results remain viewable and recoverable; only new Pro actions are blocked.
- First use without entitlement service access receives Free access. Authentication or licensing failure never switches standards or recalculates results.

## Support and diagnostics

Support begins with the generated diagnostic bundle. It contains product/build identity, supported-profile metadata, operating-system/runtime metadata, and an entitlement status label. It contains no project file or export. A user may explicitly choose one application `.log` file; the tool redacts common email, token, and local-path patterns before inclusion.

Never request an entire project folder. If engineering evidence is necessary, the customer must choose and approve each attachment through its own authorized transfer channel. Record that approval in the support case. Do not add customer evidence to source control.

Proposed internal response targets, pending counsel and pilot agreement approval:

| Severity | Example | Operating target |
|:--|:--|:--|
| Critical | Incorrect-result suspicion, data loss, security/privacy incident | Acknowledge within 4 business hours; immediately suspend affected reliance path |
| High | Pro workflow unavailable with no recovery path | Acknowledge within 1 business day |
| Normal | Usage question, export compatibility, enhancement | Acknowledge within 2 business days |

An incorrect-result suspicion is never handled as an ordinary support question. Preserve the version, inputs under the customer's control, expected/actual comparison, and affected scope; notify the release and engineering acceptance owners; block distribution or reliance on the affected path until disposition.

## Version pinning and updates

- Pilot access points and desktop artifacts identify one approved application version, engine version, criteria profile ID/revision, commit, and hash.
- Do not silently auto-update pilot users.
- Release notes separate calculation-impacting changes from application-only changes.
- A standards-profile update creates a new immutable profile identity and follows engineering change control.
- Before rollout, complete automated validation, private engineering review as applicable, clean-machine acceptance, representative-file acceptance, support readiness, and rollback rehearsal.
- Entitlement snapshots may authorize a plan and version range; they never provide or alter engineering inputs.

## Incident and rollback procedure

1. Open an incident record with time, reported version/profile, scope, and reporter; omit engineering content unless explicitly authorized.
2. Preserve the current release, diagnostics, and private evidence. Do not overwrite the affected project.
3. For suspected incorrect results, disable distribution or the affected professional action without altering stored results.
4. Release and engineering owners decide whether to restrict, revoke, or replace the release. Entitlement changes cannot recalculate or substitute criteria.
5. Notify affected named users using counsel-approved language and provide project-recovery instructions.
6. Restore the last approved signed version and verify its hash/signature. Keep existing results readable and let users export a recovery copy.
7. Re-run the relevant engineering vectors and acceptance protocol before re-enabling the path.
8. Record root cause, affected versions, corrective action, renewed review, and closure approval.

## Offboarding

- Remove the named seat and invalidate future entitlement refreshes.
- Explain grace/expiry and local recovery before access changes.
- Do not delete local customer projects or results.
- Retain entitlement/audit and support records only for the attorney-approved period.
- Confirm any desktop-use termination requirements from the approved license.

## Payment activation gate

Payment and automated Pro activation remain disabled until all required private records are signed, counsel-approved terms are effective, supported-file acceptance is complete, support ownership is assigned, and a rollback release is retained. Checkout success alone never grants Pro; a verified billing webhook must update the internal entitlement ledger before a signed Pro snapshot is issued.
