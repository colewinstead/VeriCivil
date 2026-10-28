# Superelevation Calculator repository guidance

## Engineering safety

- Treat formulas, lookup tables, stationing, ORD mappings, coordinate transforms, and generated engineering results as frozen unless a clear defect is identified and explained first.
- Keep desktop and browser behavior on the shared Python engine; do not duplicate calculation logic in the browser UI.

## Versioned merges

- `main` is user-ready. Changes beyond documentation become a GitHub Release containing the browser build and unsigned Electron desktop previews.
- Documentation-only changes (`.md`, `.rst`, and license files) do not require a version bump and do not create a GitHub Release. The `validate-version` job still runs and passes for these changes.
- Increase `APP_VERSION` in `app_info.py` beyond the latest release for changes to application code, calculation data, tests, dependencies, builds, or workflows. Mixed documentation and code changes require a version bump.
- Do not merge when `validate-version` or any other required check is red.
- Create a short-lived branch for each issue from the latest `origin/main`, such as `fix/123-export-error`, `feat/123-new-calculator`, or `docs/123-workflow`. Open PRs from that branch into `main`; do not use `dev` as a permanent integration branch.
- Enable automatic deletion of merged head branches on GitHub. After merging, start the next issue from updated `main`; remove local issue branches only after confirming their work is merged and the working tree is clean. Do not reuse merged issue branches.
- Use squash merges for PRs into `main`, producing one commit per PR; do not use merge commits or rebase merges.
- Keep only squash merges enabled in GitHub's PR merge settings and the `main` ruleset's allowed merge methods. Preserve all other branch protections and required checks.
- If `main` advances while a PR is open and GitHub requires an update, merge the latest `origin/main` into the issue branch and let required checks rerun.

## Issues and pull requests

- Start planned fixes and features with a GitHub issue describing the problem, expected behavior, and acceptance criteria. Reuse an existing issue when it covers the work.
- Create the issue branch through the issue's Development section on GitHub or `gh issue develop` so the branch is linked to the issue. Keep implementation on that branch and link the issue in the PR description. Use `Closes #<number>` for each issue fully resolved by the PR; use `Related to #<number>` for partial work so the issue remains open.
- State what changed and what validation actually passed in the PR. Leave checklist items unchecked until verified, and explain when a PR has no related issue.
- Issues linked with closing keywords close automatically when the PR merges into `main`; creating the PR or pushing to the issue branch does not close them.

## Validation

- Run `python3 -m unittest -v` on macOS/Linux or `python -m unittest -v` on Windows.
- From `web`, run the TypeScript check, lint, production build tests, and Pyodide parity tests before browser releases.
- Version-bumped PRs automatically build and verify Electron previews for Apple Silicon, Intel Mac, and Windows x64. PR builds upload Actions artifacts; successful `main` release jobs attach the desktop DMGs/portable Windows ZIP and checksums alongside the browser archive. Never publish a public release from a PR run.
- Legacy Tkinter EXE/DMG workflows remain manual-only rollback tools. The Electron preview has no production licensing or in-app updater; keep that status explicit in release documentation.
- Preserve signing keys outside the repository. Automated GitHub executables are unsigned; signed pilot releases use the private Windows signing workflow and `scripts/verify_windows_release.ps1`.

## Website publishing

- After a successful merge and GitHub Release, invoke `$ship-main` or ask Codex to “Ship main.”
- Publish only to the existing ChatGPT Site identified by `web/.openai/hosting.json`. Never create a replacement site, change its slug, or change its access policy unless the user explicitly requests that change.
