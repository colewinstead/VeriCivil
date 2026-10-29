# AASHTO redistribution clearance

Status: unresolved. This is an unsent request draft and an action plan, not permission or a legal determination. Do not include the supplied publication PDF, private workbook/CSV, or private project files in a public issue or an unsolicited upload.

## How to resolve it

1. Ask AASHTO Publications for written permission covering the actual software distribution and downstream reuse described below. Start at the [Copyright Permissions page](https://store.transportation.org/Page/CopyrightPermissions). If it does not expose a request mechanism, use the **Publications Questions** form on [Contact Us](https://store.transportation.org/ContactUs) to request the correct permissions contact. The current permissions landing page did not expose a detailed application form when checked on October 28, 2026.
2. Identify the exact edition, errata, source locations, transcribed data, repository, and distribution formats. Supply any requested excerpt or pre-publication sample privately through the channel AASHTO specifies, after reviewing its terms. Ask for treatment of existing repository/release copies as well as future distribution.
3. Obtain terms allowing public source distribution, browser-delivered runtime data, downloadable offline desktop binaries, modifications, downstream redistribution, and possible commercial sales. Ask explicitly whether these rights can accompany an OSI-approved open-source project. A personal-use or internal-use permission alone does not cover this model. Ask about attribution, fees, duration, territory, revocation, and required source/table notices.
4. Alternatively, obtain qualified legal review of whether the particular numeric facts, selection/arrangement, extraction, and source acquisition/license terms permit this reuse without publisher permission. The general distinction between facts and copyrightable compilations does not itself clear this dataset. Do not treat credit, buying the book, hiding grids, free downloads, or an MIT license as permission.
5. If appropriate rights cannot be established, plan a separate engineering-reviewed change to remove the bundled AASHTO data/profile from distributable artifacts, or use a separately licensed user-supplied data mechanism whose terms permit that use. A publicly accessible FHWA/DOT workbook is not automatically a rights-cleared replacement. Check provenance and terms first. Removing the data from the current file alone would not address old tags, release archives, or deployed runtime copies; decide any remediation with the rights holder/adviser before changing history or releases.

Preserve formulas and tables while the rights decision is pending. Do not mark the [rights record](AASHTO_2018.md#sources-and-rights) cleared until the permission/review covers the shipped material and distribution model. Record the grant date, scope, attribution, downstream conditions, and any expiry; keep private correspondence private. Confirm compatibility with SignPath before representing the complete package as eligible. Signing does not clear data rights.

## Request draft — review before sending

Subject: Permission request: Green Book 2018 numeric data in VeriCivil open-source software

Hello AASHTO Publications Permissions Team,

My name is Cole Winstead. I maintain VeriCivil Superelevation Calculator, a roadway engineering tool at https://vericivil.com, with public source at https://github.com/colewinstead/VeriCivil.

I would like to establish the permissions required to redistribute numeric material derived from *A Policy on Geometric Design of Highways and Streets*, seventh edition (2018), including the October 2019 errata, in this software. Our current implementation references Tables 3-8 through 3-12, Table 3-15, Table 3-16a, Equations 3-23 through 3-25, and related transition guidance. The precise implementation scope and exclusions are documented at https://github.com/colewinstead/VeriCivil/blob/main/docs/AASHTO_2018.md. The transcribed numeric data are embedded in `aashto_tables.py` and consumed by our shared calculation engine. We are not proposing to redistribute the publication PDF, scanned pages, or the private source workbook/CSV.

The code is currently MIT-licensed. Desktop tools are currently free; the website also offers paid workflow access, and we may charge for software or services in the future. Numeric data embedded in public source or browser runtime files can be inspected and copied by recipients, even if full table grids are not displayed in the interface. Our public repository and published software artifacts already contain this transcription; our documentation records that publisher redistribution permission has not been established. Please advise about existing copies as well as the steps needed to authorize future distribution.

We seek written permission or applicable licensing terms covering:

- Public source hosting and version history containing the transcribed data.
- Distribution in browser/WebAssembly runtime assets and offline Windows/macOS application packages, installers, and updates.
- Use in calculations, generated project-specific reports/exports, and validation tests.
- Modification and downstream redistribution of the software/data by open-source recipients, including free and commercial distributions worldwide.
- Attribution, edition/errata notices, and any restrictions necessary to distinguish our implementation from AASHTO endorsement or certification.

Please confirm whether you can grant rights compatible with distribution as part of an OSI-approved open-source project, or identify an appropriate alternative license. Please also specify fees, term, territory, revocation conditions, source-access limitations, and whether end users or downstream redistributors require separate permission. A permission limited to my own internal use would not cover the intended distribution.

I can provide the exact implementation excerpt and representative outputs privately through your preferred review channel. Please let me know the appropriate next steps and any required application materials.

Thank you,

Cole Winstead
VeriCivil Superelevation Calculator
https://vericivil.com

## Clearance record

- Contact/request date: not sent.
- Permission or legal review reference: none.
- Public-source and browser-runtime redistribution: not established.
- Offline desktop and updater redistribution: not established.
- Downstream modification, redistribution, and commercial sales: not established.
- Required notices/fees/expiry: unknown.

Sources checked October 28, 2026: [AASHTO permissions](https://store.transportation.org/Page/CopyrightPermissions), [AASHTO Publications contact](https://store.transportation.org/ContactUs), [U.S. Copyright Office on databases and compilations](https://www.copyright.gov/register/tx-databases.html).
