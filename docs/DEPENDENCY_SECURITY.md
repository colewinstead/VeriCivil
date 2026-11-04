# Dependency security update: application 1.7.4

This update is based on the cross-section branch, including its README changes, and is tracked by issue #82. It updates npm packages and application release metadata; engineering formulas, criteria data, project formats, and export calculations are unchanged. It does not deploy the website or publish desktop installers.

## Audit snapshot

The following counts describe the committed lockfiles and the npm advisory database at validation time. An affected package can also flag packages above it in the dependency tree; the total is not a count of distinct exploitable application paths.

| Audit | Before | After |
| --- | --- | --- |
| Full browser/build tree | 59: 1 critical, 16 high, 41 moderate, 1 low | 31 moderate; no critical, high, or low entries |
| Browser production dependencies (`--omit=dev`) | 6: 1 critical, 4 high, 1 moderate | 0 |
| Desktop runtime dependencies (`desktop/package-lock.json`) | 0 | Unchanged; 0 |

The before snapshot is from cross-section commit `ceb376e`. Reproduce the reports from the repository root with:

```sh
npm --prefix web audit
npm --prefix web audit --omit=dev
npm --prefix desktop audit
```

The full audit still exits nonzero because the moderate findings remain. No findings have been hidden or excluded from that report. Production-only dependency classification is not an assessment of the deployed bundle: some development dependencies generate or supply server code, and deployment-specific exploitability was not independently tested.

## Targeted updates and overrides

- Next.js and its ESLint configuration: `16.2.6` → `16.4.4`.
- React, React DOM, and React Server DOM Webpack: `19.2.6` → `19.2.8`, retaining a matched release line.
- Vite: `8.0.13` → `8.3.5`; Cloudflare Vite plugin: `1.37.1` → `1.67.0`; Wrangler: `4.92.0` → `4.156.2`. Workers types move to `5.20261102.1` to satisfy the updated Wrangler peer requirement.
- Drizzle Kit: `0.31.10` → `0.31.11`. Compatible transitive updates include Babel, Browserslist, brace expansion, URI parsing, YAML, Zod, esbuild, and browser mapping data.
- Update the existing PostCSS override from `8.5.14` to `8.5.32`.
- Keep Vinext `0.0.50` and override its pinned `image-size` dependency to `2.0.4`. This avoids a framework-major migration solely to update the image parser.
- Override `@vercel/og`'s Satori to `0.33.5`, and affected `fflate` 0.7.x dependencies to `0.7.5`. The image compatibility test exercises default-font PNG rendering and dimension extraction.
- Override only the deprecated `@esbuild-kit/core-utils` loader's esbuild to `0.25.12`. Its synchronous/asynchronous TypeScript transforms are tested, and Drizzle schema generation is checked in a temporary directory against in-memory SQLite. No live database or tracked migration is modified by that check.

Keep these overrides explicit until their parent packages adopt fixed dependencies. Remove them together with their dedicated compatibility checks when a compatible upstream update makes them unnecessary. ESLint, Electron Packager, and Electron Builder retain their current major versions; `npm audit fix --force` is not used.

## Remaining findings

The 31 moderate package entries trace to two underlying advisories in build/lint/package tooling:

| Advisory | Remaining boundary |
| --- | --- |
| [Minimatch glob-pattern amplification](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249) | npm flags versions below `11.0.1`; maintained tool dependencies still select older major versions. A blanket override to Minimatch 11 changes APIs relied on by callers. |
| [Glob cancellation bypass](https://github.com/isaacs/node-glob/security/advisories/GHSA-3g3m-2fjr-6pw4) | Affected newer Glob versions remain in packaging dependencies. Replacing them with patched Glob 14 would cross their declared compatibility ranges. |

These are unresolved findings, not false-positive suppressions. Address them through compatible upstream tool updates or a separately validated tooling-major migration. Build and lint trusted source; this update does not establish that attacker-controlled patterns or file trees are safe.

## Validation and rollback

Validation covers a clean `npm ci --ignore-scripts`, TypeScript, lint, production build, browser policy/render tests, native/Pyodide parity, the Python suite, desktop unit tests, actual offline Electron project/export/security checks, and browser/Electron cross-section interaction checks. The image and TypeScript-loader compatibility checks run in `npm test`. The cross-section smoke now reads the generated application version instead of assuming version 1.7.3.

The local run passed 277 Python tests, 57 browser tests, and 11 desktop unit tests. Lint passed with one existing `pendingRef` cleanup warning in `CalculatorApp.tsx`. Desktop interaction checks ran on macOS; Windows and Intel Mac preview packaging remain CI checks. No live payment, deployment, signing, or production-database validation was performed.

Before release, rollback means reverting the dependency-update commit and reinstalling from the restored manifest and lockfile together. After a public release, restore those dependency files in a new versioned PR while keeping `APP_VERSION` increasing. There is no project-data or database migration to reverse. Signing, publishing, and Site deployment remain separate authorized release steps.
