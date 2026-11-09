# Guardrail browser integration

VeriCivil's free `/calculators/guardrail` workspace uses the separately maintained
[Guardrail Calculator](https://github.com/colewinstead/Guardrail-Calculator).
The calculation engine and report modules are bundled unchanged from commit
`c5df84ad9376442e6ba0cac1d37611a3cd34df2b` (V8.5.2). The exact source files,
bundled references, upstream characterization fixture, MIT license and SHA-256
checksums are recorded in `calculators/guardrail/upstream/source.json`.

## Ownership and updates

- Fix calculations, tables, parsing, validation and existing report behavior in
  **Guardrail-Calculator** first. Its Windows application remains independently maintained.
- Maintain browser controls, JSON project format and runtime adaptation in
  **VeriCivil**, principally `calculators/guardrail/service.py` and
  `web/app/GuardrailCalculator.tsx`.
- Never edit files under `calculators/guardrail/upstream/` directly. The browser
  staging step verifies their checksums and fails if they change.
  `.gitattributes` disables Git line-ending conversion for this imported directory
  so Windows checkouts retain the exact upstream bytes.

After the upstream change is reviewed and tested, create an issue-linked VeriCivil
branch from current `main`, check out the desired Guardrail commit locally, and run:

```sh
python3 scripts/update_guardrail.py --source /path/to/Guardrail-Calculator --revision FULL_40_CHARACTER_COMMIT_SHA
python3 scripts/update_guardrail.py
python3 -m unittest -v
cd web
npm exec tsc -- --noEmit
npm run lint
npm test
```

The importer reads committed Git objects; uncommitted upstream edits are excluded.
Review the source and dependency changes, pin and checksums, upstream fixture changes,
browser/native parity and generated reports in the upgrade PR. A changed fixture is
evidence to investigate, not a reason to replace the expected digest automatically.
Update the integration documentation, manifest limits and application version as
needed. Rollback means a normal PR restoring the earlier imported revision, with
VeriCivil's required new application version.

No GitHub connection is needed by site visitors or by the normal source build.
Runtime dependencies load through VeriCivil's existing Pyodide worker. Initial
browser loading needs internet access; this is not an offline-availability guarantee.
The worker stages reference PDFs as binary assets into its local virtual filesystem.

## Included workflow

Both current facility types, near/opposing calculations, direct or table-selected
LA, custom clear zone, standard/custom transition and terminal lengths, supported
flare ratios and non-flared mode are retained. Divided-roadway opposing distances
can remain manually entered or be linked to the lane/median dimensions. Linked
values are resolved by upstream Python, without JavaScript engineering arithmetic.

All three report styles reuse the upstream report layout. Optional appendices
include `gr manual.pdf` plus `GR-4.pdf` for divided highways or `GR-4a.pdf` for
two-lane/two-way highways, with their original page sizes. Missing references fail
the requested export rather than silently producing an incomplete package.

Version 1 `vericivil.guardrail` JSON files contain raw inputs, mode selections,
project metadata, PDF preferences, source commit and engine version. Imports are
limited to 64 KiB and validate supported fields, types, selections and active
engineering inputs before replacing current state. Saved results are never trusted:
reopening recalculates. A changed source revision is reported to the user. These
files do not establish Windows project-file interoperability. File downloads are
browser-managed; keep the downloaded JSON to reopen the project. There is no cloud
project storage or automatic session recovery.

Input edits immediately hide the old result and disable export until calculation
succeeds. Downloads use one captured set of inputs. Unsaved-change warnings cover
page unload, navigation links and project replacement, subject to browser limits
on unload prompts (especially on mobile). Saving a PDF does not save the project.

## Validation and engineering boundaries

`test_guardrail_browser.py` exercises the new JSON boundary against the upstream
2,592-case numerical baseline and 12 report-payload/page fingerprints. The same
tests run natively and through `web/tests/guardrail-parity.mjs` in Pyodide, including
both facility-specific appendix packages. `web/tests/guardrail-smoke.mjs` tests the
rendered page, automatic calculation, stale-result protection, JSON download/reopen,
PDF downloads, malformed imports, responsive layouts and unsaved navigation.

Run the renderer smoke with the dev server running at `http://localhost:3001`
using `npm run test:guardrail:browser` from `web`. Set `GUARDRAIL_TEST_URL` to the
full calculator URL when using another port. On hosts inheriting
`ELECTRON_RUN_AS_NODE=1`, run `env -u ELECTRON_RUN_AS_NODE npm run test:guardrail:browser`.
The renderer test writes local desktop/phone captures under the ignored
`.impeccable/review/guardrail/` and refreshes the catalog's authentic result crop.
When adopting a new crop, embed its screenshot origin with Impeccable's
`embed-prompt` command before committing.

These are software regression and integration checks, not independent engineering
approval. Preserve the upstream architecture's unresolved questions about clear-zone
interpretation, traffic direction/physical sides, terminal contributions, minimum
rail lengths, opposing-hazard geometry and ADT table boundaries. Reports preserve
the upstream contents; the existing sheet does not record the complete LA-selection
provenance. Verify inputs, references, assumptions and applicability for the project.
The upstream license accompanies its source; included MDOT PDFs are reference
material, not a claim that the upstream MIT license licenses agency publications.

DXF and LandXML overlays remain in the separate Windows application. This browser
integration does not extend their support or change their engineering restrictions.
