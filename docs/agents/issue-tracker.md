# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `colewinstead/VeriCivil`.
Use the `gh` CLI from this repository.

Follow the issue, branch, and PR workflow in the root `AGENTS.md`.

## Operations

- Verify the target: `gh repo view --json nameWithOwner`.
- Create: `gh issue create --title "..." --body-file <file>`.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open --json number,title,labels`.
- Comment: `gh issue comment <number> --body-file <file>`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` or
  `--remove-label "..."`.
- Close: record the resolution before closing. Issues fully resolved by a PR
  close through `Closes #<number>` when that PR merges into `main`.

Use a UTF-8 file containing actual newlines for multiline bodies.
Before creating an issue, check for an existing issue covering the work.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Skill terminology

“Publish to the issue tracker” means create a GitHub issue.
“Fetch the relevant ticket” means read the GitHub issue.
