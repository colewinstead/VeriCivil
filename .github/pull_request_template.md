## Linked issues

<!-- Add Closes #<number> for each issue fully resolved, one per line.
Use Related to #<number> for partial work. Explain if no issue applies. -->

## What changed

<!-- Describe the problem and resulting behavior. -->

## Validation

<!-- List checks actually run and their results. Explain relevant checks not run. -->

## Release-ready checklist

- [ ] Relevant issues are linked, or the absence of an issue is explained.
- [ ] `APP_VERSION` is newer than the latest GitHub Release, or this PR changes only documentation/license files.
- [ ] The change is ready for users; non-documentation changes create a full release on merge.
- [ ] Calculation behavior is unchanged, or the proven engineering defect and its verification are documented.
- [ ] Required checks pass, and any applicable Windows validation is recorded above.
- [ ] For a release requiring a website update, plan to invoke `$ship-main` after the GitHub Release succeeds.
