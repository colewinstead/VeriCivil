# Paid Pilot Readiness Assessment and Roadmap

Current distribution scope (November 9, 2026): free, unsigned Windows x64 desktop builds; code signing work and Mac desktop builds are paused. The commercial-pilot requirements below are a separate historical assessment, not prerequisites for the active unsigned public release channel. See [current desktop readiness](desktop-production-readiness.md).

## 2026-07-19 commercial-foundation update

The owner reports that PE validation has been completed for the recorded calculator version and scope; the controlled evidence and reviewer identity remain outside this public repository. This is not a public or personal PE-certification claim, does not automatically cover later engineering-behavior changes, and does not replace independent verification by the responsible project PE. See `docs/COMMERCIAL_READINESS.md` for the current commercial status, entitlement architecture, remaining legal and acceptance blockers, and user-responsibility position. The original assessment below is retained as the baseline that defined the validation work.

## Executive conclusion

The application has a useful modular calculation/export core and a meaningful automated-test baseline, but it is not yet ready to be represented as validated commercial roadway-engineering software. The dominant blocker is engineering traceability: the governing MDOT publications and revisions are now identified, but value provenance, implementation assumptions, and independent golden calculations are not established. Legal terms, a signed/validated Windows release, and real ORD/customer acceptance evidence are also required before money or production reliance is involved.

The original readiness changes improved identification, diagnostics, compatibility, and build repeatability. Engine `1.2.4` centralizes MDOT lane profiles, keeps runoff segments linear, applies the SE-3A `X1 = Lr(NC/e)` breakpoint to the inside-lane rotation, and corrects normal-crown event labeling. Explicit reverse-curve pairs delete only the tangent runout between selected eligible opposite-direction curves, require `Tmin = 0.7Lr(exit) + 0.7Lr(entry)`, and preserve each curve's standard `e/Lr` rate with lane-specific continuous handoffs or normal-crown holds. A valid unequal-rate handoff may occur just before PT or just after PC but must stay between the two unchanged full-super stations. A normal-crown hold is validated and reported using only its real start and end boundaries. Short or invalid pairs block without altering the independent results. These changes require version-specific engineering review. The separately selectable `tdot-rd11-2026-04-30` profile remains unchanged. The TDOT profile transcribes the desirable RD11-LR-1/RD11-LR-2 tables and RD11-SE-1 rules with golden and boundary tests, but still requires independent engineer review before production reliance. See [`MDOT_TRANSITION_MODEL.md`](MDOT_TRANSITION_MODEL.md) for the source record and model boundaries.

## Architecture and evidence reviewed

- `Super.py`: station conversion, formulas, lookup tables, overrides, and formatted results.
- `super_lane.py`, `super_exports.py`, `super_batch.py`: lane profiles, normalized events, batch calculations, and ORD CSV.
- `super_landxml.py`: LandXML 1.2 first-alignment parser and line/arc station geometry.
- `super_dxf.py`, `super_pdf.py`: CAD and report generation.
- `super_project.py`: JSON persistence and compatibility.
- `super_app.py`: current Tkinter desktop UI.
- `super_ui.py`: legacy UI and embedded PNG source-sheet/logo assets used by PDF output.
- Tests, synthetic LandXML, workflows, PyInstaller spec, requirements, README, SVG, and ORD add-in research.

The pre-change baseline was 44 passing tests on the review host. Embedded base64 assets decoded as valid PNG files; decoding does not establish publication authenticity, revision, copyright permission, or engineering approval.

## Engineering traceability finding

`Super.py` references Table 3-4-A/B/C, Equation 3-4-1, SE-1, SE-2A–E, and SE-3A–B. These identifiers are now tied to MDOT's *2020 Roadway Design Manual* and *Roadway Design Standard Drawings* compilation revised April 22, 2026. The individual SE sheets show an issue date of August 1, 2017. `tdot_criteria.py` separately records TDOT RD11-LR-1/RD11-LR-2 radius rows and RD11-SE-1 gradient/lane factors; the RD11 typical-section catalog is supporting provenance rather than an automatically enforced width, grade, or sight-distance model. The implementation also describes some MDOT fallback behavior only as “AASHTO-style,” uses a `DEFAULT_FRICTION_SCALE = 0.24`, performs nearest-row and interpolation choices, caps rates for area/speed cases, and accepts manual overrides. The repository still does not establish:

- a complete criterion-to-page/sheet matrix or confirmation that no later design memo supersedes a cited rule;
- a value-by-value transcription review for every embedded table;
- why the friction scaling and fallback formula are appropriate for each enabled facility/area case;
- which rounding, interpolation, nearest-row, minimum/maximum, and out-of-range rules are explicitly governed versus implementation assumptions;
- who may authorize an override, why it was used, or where the approval is recorded;
- independent hand calculations or agency-approved examples covering every branch;
- change control requiring engineering approval when criteria or code changes.

Therefore the current criteria are source-identified but cannot yet be called validated. The metadata intentionally records that distinction rather than treating an identified publication date as proof that every implemented value and rule is correct.

## Phase 1 — reliable paid pilot for 3–5 engineers

Phase 1 contains only work needed to run a controlled, supported pilot. “Block” means it should prevent accepting payment or allowing engineering reliance until complete.

| Item | Why it matters | Risk if omitted | Likely files/modules | Difficulty | Blocks pilot | Recommended implementation approach |
|:--|:--|:--|:--|:--:|:--:|:--|
| Engineering criteria traceability and independent validation | Roadway outputs must be reproducible against the governing standard. | Incorrect design decisions, professional-liability exposure, and no defensible calculation record. | `Super.py`, `criteria_info.py`, new controlled criteria matrix and golden fixtures | High | **Yes** | A qualified roadway engineer must identify the issued sources and revision; map every constant/table/formula/branch/rounding rule; double-check transcription; approve hand calculations for all facility/area/speed/crown/override paths; retain signed evidence. Disable any unverified path. |
| Override provenance and approval | Overrides can supersede automatic criteria and materially change results. | Undocumented departures may be mistaken for governed values. | `Super.py`, `super_app.py`, `super_project.py`, `super_pdf.py` | Medium | **Yes** | Require reason, source/reference, author, date, and reviewer for each active override; show them prominently in UI/report; warn before export if incomplete. Preserve current override arithmetic. |
| Authoritative application/engine/schema identity | Support and calculation reproduction require exact versions. | Two engineers may produce different outputs with no way to tell why. | `app_info.py`, `Super.py`, `super_app.py`, `super_pdf.py`, `super_project.py` | Low | Yes | **Implemented:** single app version, separate engine version, UI/PDF/project metadata, schema v5. Enforce version bump policy during release review. |
| Backward-compatible project schema | Pilot users must reopen work safely across builds. | Silent loss/misinterpretation or corrupted project files. | `super_project.py`, compatibility fixtures/tests | Medium | Yes | **Implemented:** v1/v2 migration, legacy provenance, future-version refusal, atomic writes. Before pilot, add sanitized real v1/v2 fixtures and documented backup/rollback tests. |
| Structured logging and actionable errors | A 3–5 person pilot needs support without developer access. | Users become blocked or share screenshots/raw customer files unnecessarily. | `app_logging.py`, `super_app.py`, parser/export modules | Medium | Yes | **Implemented:** rotating local log, operation-specific messages, open-log-folder prompt. Before pilot, exercise failures from the signed EXE and document safe log redaction/sharing. |
| Windows executable build reproducibility | Engineers need the same identifiable binary. | One-off builds, missing assets/dependencies, and unverifiable support state. | `SuperElevation.spec`, `scripts/`, workflow | Medium | Yes | **Implemented in source:** clean PowerShell build, generated version resource, checksum, explicit modern entry point. Must still run and retain evidence on supported Windows. |
| Signed installer and clean-machine acceptance | Normal users need a trustworthy install/uninstall path. | SmartScreen blocks, antivirus alerts, permissions failures, or unsigned-code trust concerns. | `packaging/Superelevation.iss`, signing/release infrastructure | Medium | **Yes** | Installer definition is present but unverified. Obtain Authenticode certificate, sign/timestamp EXE and installer, test standard-user install/uninstall on each pilot image, and regenerate checksums after signing. |
| Controlled update/rollback delivery | Pilot users must know which build is approved. | Version drift, accidental downgrade, or inability to recover. | GitHub/private release channel, release docs | Medium | Yes | Use manual immutable signed releases with hashes, release notes, user/version register, prior-installer rollback, and explicit update notice. Do not add silent auto-update during the pilot. |
| Real workflow acceptance | Synthetic tests cannot prove interoperability with customer files/ORD. | CSV may import incorrectly; DXF coordinates or report layout may fail on real projects. | acceptance fixtures, `super_landxml.py`, exports, release evidence | High | **Yes** | Use sanitized representative alignments including equations and unit variants; perform real ORD CSV round trips and DGN DXF overlays; compare PDFs/projects to approved expected outputs. Keep customer data outside the public repo. |
| Pilot documentation and onboarding | Engineers need limitations and independent-check instructions at the point of use. | Misuse of unsupported geometry, stationing, units, or lane mapping. | README, in-app help, pilot guide | Medium | Yes | Provide a short install/first-project guide, supported-input matrix, spiral limitation, override rules, ORD/DXF checklist, backup/update/rollback, log-sharing/privacy, and engineering-aid disclaimer accepted by each pilot user. |
| Commercial license/EULA/support terms | Public source visibility does not define paid-use rights or responsibility. | Contract, IP, warranty, and support disputes. | legal documents; distribution package | High | **Yes** | Engage qualified counsel; define license scope, seats, term, confidentiality, data handling, warranty/liability, engineering responsibility, support, termination, third-party notices, and source/assets rights. Do not infer an open-source license. |
| Customer-data protection baseline | Project names, paths, geometry, and reports may be confidential. | Accidental disclosure through public issues, logs, backups, or fixtures. | UI/docs/logging/release process | Medium | Yes | Confirm local-only processing; prohibit telemetry/upload for pilot; document stored files/log paths and retention; redact logs; use sanitized fixtures; restrict release/support storage; threat-model project and XML parsing. |
| Automated regression and release gates | Engineering behavior needs durable evidence. | A UI/export fix may alter calculations unnoticed. | all tests, workflows, release checklist | Medium | Yes | **Partly implemented:** metadata/error/schema tests and synthetic file smoke test. Add approved golden numeric vectors for every calculation branch and run the signed-build acceptance checklist before pilot. |

## Phase 2 — broader commercial release

| Item | Why it matters | Risk if omitted | Likely files/modules | Difficulty | Blocks paid pilot | Recommended implementation approach |
|:--|:--|:--|:--|:--:|:--:|:--|
| Versioned external criteria packages | Criteria maintenance should be reviewable without editing a large engine. | Transcription drift and opaque code reviews. | `tdot_criteria.py`, split remaining MDOT tables, new schemas/data validators | High | No | **Partly implemented:** TDOT tables are isolated behind a versioned profile. After pilot validation, move remaining immutable criteria into signed/versioned data files; validate schemas/checksums; require engineering approval and golden regression updates. Preserve exact arithmetic during extraction. |
| Expanded LandXML support | Real alignments commonly include spirals, multiple alignments, namespaces, and varied units. | Excluded customers or unsafe partial geometry. | `super_landxml.py`, `super_dxf.py`, fixtures | High | No, if pilot inputs exclude them | Implement schema-aware multi-version parsing, explicit alignment selection, complete geometry validation, and spiral evaluation with independent geometry tests. |
| Production update client | Larger deployments need discoverable, secure updates. | Persistent vulnerable/incorrect versions or unsafe downloads. | new update service/UI, release signing | High | No | Check a signed HTTPS manifest only on user request or admin schedule; verify signature/hash before install; show release notes; support deferral and rollback; never send project data. |
| Installer lifecycle and enterprise deployment | Broader customers may require MSI, managed deployment, and admin controls. | IT rejection and inconsistent installs. | packaging/CI/signing | High | No | Evaluate MSI/MSIX versus signed Inno installer; add silent install/uninstall, per-machine option, upgrade codes, enterprise detection, SBOM, and reproducible build evidence. |
| Observability/support bundle | More users require efficient, privacy-aware diagnosis. | High support cost and over-sharing. | logging, diagnostic exporter, docs | Medium | No | Add redacted support bundle with versions, OS, dependency/build ID, recent logs, and opt-in attachment selection; never include project files automatically. |
| Security hardening program | File parsers and update mechanisms expand attack surface. | Malicious input, dependency compromise, or data leakage. | dependencies, parsers, CI, update path | High | No | Pin/review dependencies, generate SBOM, scan builds, fuzz XML/JSON, impose file/complexity limits, review XML parser posture, sign releases, protect keys, establish vulnerability disclosure and patch SLAs. |
| Broader OS/ORD compatibility matrix | Commercial claims must specify supported environments. | Unbounded support and environment-specific failures. | CI, VM lab, acceptance suite | High | No | Define Windows/ORD versions; test each clean image; retain real import/overlay evidence; publish compatibility and deprecation policy. |
| Accessibility and usability validation | A broader user base needs consistent, accessible workflows. | Input mistakes and adoption barriers. | `super_app.py`, documentation | Medium | No | Test DPI/scaling, keyboard navigation, focus, screen readers, color contrast, long paths, locale/decimal behavior, and warning comprehension with roadway engineers. |
| Licensing enforcement/entitlements | Wider sales may need controlled access. | Unmanaged redistribution or burdensome manual administration. | new licensing layer/service | High | No | Choose privacy-preserving offline/online entitlements after legal/product design; include grace periods and support recovery; licensing must never alter calculation results. |
| Maintainable architecture and asset provenance | Legacy duplicate UI and embedded assets increase review/build burden. | Divergent behavior, unclear copyright, and large opaque source. | `super_ui.py`, `super_pdf.py`, asset packaging | Medium | No | Remove the legacy fallback after migration, package approved assets separately with provenance/licenses, isolate UI/services, type models, and enforce dependency boundaries. |
| Expanded automated assurance | Commercial scale needs more than example-based unit tests. | Edge-case regressions across stations, tables, and files. | tests/CI/fixtures | High | No | Add boundary/property/metamorphic tests, corruption/fuzz cases, visual PDF/DXF checks, installer tests, performance limits, and mutation/coverage reporting without using coverage as a substitute for engineering validation. |

## Current update, licensing, and data posture

- Every desktop launch performs one non-blocking request to GitHub's public latest-release endpoint. A newer version opens an explicit download prompt; current-version, offline, and invalid responses remain silent. Download, installation, and rollback remain manual, with no background installer behavior.
- The repository has no open-source license and no commercial EULA. Public visibility does not grant reuse rights, but it also does not supply customer contract terms.
- Calculation and project processing is local. The update request sends no project, LandXML, calculation, file-path, or telemetry data. Exports and logs remain wherever the user saves them; diagnostic logs contain exception details and can contain local file paths.
- Dependencies are range-pinned, not hash-locked, and there is no SBOM or vulnerability-response process.

## Items that still block a paid pilot

1. Qualified-engineer approval of governing sources, every embedded value/formula/assumption, override policy, and golden calculations.
2. Approved commercial license/EULA, support terms, third-party notices, and confirmation of rights to embedded logos/source-sheet images.
3. A Windows build produced by the documented process, Authenticode signing/timestamping, installer validation, malware scanning, and clean-machine launch/install/uninstall evidence.
4. Real sanitized project acceptance: LandXML, PDF, project compatibility, DXF-in-DGN verification, and actual ORD CSV round-trip evidence.
5. Final pilot onboarding/limitations/privacy/support package and named release/update/rollback owner.

Spiral overlay support does not have to block a narrowly scoped pilot only if pilot inputs are screened to exclude spirals and the existing block is verified. It is a broader-release requirement.
