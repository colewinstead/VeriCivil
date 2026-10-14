---
name: ship-main
description: Publish the released main commit to VeriCivil's existing ChatGPT Site. Use for "Ship main" or requests to republish after merging.
---

# Ship Main

Publish the released `main` source to the existing Site. Invocation authorizes deployment at its current access level, without changing the Site identity, slug, domain, or audience.

## Verify the release

1. Read `AGENTS.md`, `app_info.py`, and `web/.openai/hosting.json`. Use the GitHub repository identified by `origin` and the existing Site's `project_id`.
2. Fetch `origin/main` and tags without discarding local work. Read `APP_VERSION` from that commit.
3. Confirm `vAPP_VERSION` is a published, non-prerelease release at that commit, the Full Release workflow succeeded, and its browser archive and checksum are present. Manual-only desktop builds are not required.
4. Reuse successful Python, TypeScript, lint, browser tests, and Pyodide parity checks for that exact commit. Run only missing checks; stop on failures or release mismatches. Do not modify source or repair releases as part of shipping.

## Build and publish

1. Follow the currently available Sites skill and its supported source, build, and packaging helper. Reuse a clean checkout at the released commit; create a temporary checkout only when needed to preserve local work.
2. Build the Sites production output from that source. Install declared dependencies only when missing. Do not substitute the GitHub browser archive unless it meets the current Sites archive requirements.
3. Inspect the existing Site and hosted environment-variable names. Preserve its configuration and secrets; do not upload local environment files or credentials.
4. Obtain a short-lived source credential when the helper needs it, keeping it out of output, files, command history, and Git configuration. Follow the helper's credential input protocol.
5. Synchronize the released source and package its build using the Sites helper. Save the verified pushed source commit and matching archive, then deploy that saved version at the existing access level. Never create a replacement Site.
6. If deployment is pending, poll its returned ID until terminal. On failure, report the reason; do not repeatedly deploy the same failed version.

## Finish

- Confirm deployment succeeded, and verify the custom domain and `/calculator` return HTTP 200 and expose the released app version.
- Remove only temporary files created for this run after verifying their exact paths. If cleanup is blocked, report what remains without retrying through another execution path.
- Report the live URL and app/engine versions. If GitHub or Site access is unavailable, report the blocker rather than using another repository or Site.
