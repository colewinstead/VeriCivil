# Superelevation Calculator repository guidance

## Engineering safety

- Treat formulas, lookup tables, stationing, ORD mappings, coordinate transforms, and generated engineering results as frozen unless a clear defect is identified and explained first.
- Keep desktop and browser behavior on the shared Python engine; do not duplicate calculation logic in the browser UI.

## Versioned merges

- `main` is user-ready. Changes beyond documentation become a browser GitHub Release while the desktop edition is Coming soon.
- Documentation-only changes (`.md`, `.rst`, and license files) do not require a version bump and do not create a GitHub Release. The `validate-version` job still runs and passes for these changes.
- Increase `APP_VERSION` in `app_info.py` beyond the latest release for changes to application code, calculation data, tests, dependencies, builds, or workflows. Mixed documentation and code changes require a version bump.
- Do not merge when `validate-version` or any other required check is red.
- Keep `dev` as the permanent working branch and open release PRs from `dev` into `main`. Create additional branches only when the user asks.
- Use regular merge commits for PRs into `main`, preserving the individual commits; do not squash or rebase merge.
- Merge `main` back into `dev` only when changes were made directly on `main`, such as a hotfix. Regular `dev`-to-`main` merges do not require syncing back.

## Validation

- Run `python3 -m unittest -v` on macOS/Linux or `python -m unittest -v` on Windows.
- From `web`, run the TypeScript check, lint, production build tests, and Pyodide parity tests before browser releases.
- Windows EXE and macOS DMG workflows are manual-only while desktop distribution is paused. Do not make them required PR checks or automatic `main` release jobs until the user resumes desktop releases.
- Preserve signing keys outside the repository. Automated GitHub executables are unsigned; signed pilot releases use the private Windows signing workflow and `scripts/verify_windows_release.ps1`.

## Website publishing

- After a successful merge and GitHub Release, invoke `$ship-main` or ask Codex to “Ship main.”
- Publish only to the existing ChatGPT Site identified by `web/.openai/hosting.json`. Never create a replacement site, change its slug, or change its access policy unless the user explicitly requests that change.
