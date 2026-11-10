# Release download guide

You normally need **one installer**, not the whole asset list. Open the [latest release](https://github.com/colewinstead/VeriCivil/releases/latest) and use its download table, or use [VeriCivil downloads](https://vericivil.com/downloads) for the branded edition.

## Choose your Windows edition

In the filenames below, `<version>` is the release number, such as `1.9.2`.

| Computer | VeriCivil edition: usual download | Neutral edition: no VeriCivil branding |
| --- | --- | --- |
| Windows x64 | `VeriCivil-Superelevation-<version>-win-x64-unsigned.exe` | `Superelevation-Calculator-<version>-win-x64-unsigned.exe` |

The two editions share the calculator and Python engine. Their branding, installed application identities, local profiles, and update feeds differ. Keep the same edition when updating. The website's download page offers the VeriCivil edition; the release table offers both.

The Windows `.exe` installs the app, creates shortcuts and an uninstaller, and supports approved in-app updates. `x64` means 64-bit Intel/AMD Windows. Code signing work and all Mac desktop builds are paused. Older releases keep their historical Mac assets; new releases publish Windows desktop builds only.

**Unsigned evaluation builds:** these Windows downloads are not publisher-signed. Windows updates use HTTPS and SHA-512 checksums without publisher-signature verification. See the [code signing policy](https://vericivil.com/code-signing).

## What is published now?

| Group | Purpose |
| --- | --- |
| Windows installers | One unsigned `.exe` for each edition. Choose the edition you already use. |
| Windows portable previews | One `.zip` per edition. Extract the whole folder; replace it manually to update. |
| `SHA256SUMS-*.txt` | Download integrity checks for installers, previews, and the browser archive. |
| `latest-*-unsigned-win32-x64.yml` | One Windows installer update feed per edition. The app reads these; do not install them yourself. |
| `Superelevation-Browser-<version>.tar.gz` | Browser build archive for hosting, not a desktop installer. |
| GitHub source archives | Developer source snapshots, not compiled applications. |

Older releases such as v1.9.0 also contain Apple Silicon and Intel Mac packages and their checksums. Those assets are historical; their presence does not indicate ongoing Mac builds. Existing releases are not being deleted or renamed.

## What do the other filenames mean?

- `Superelevation-Desktop-Preview-...` is the VeriCivil preview. `Superelevation-Calculator-Desktop-Preview-...` is the neutral preview. A Windows preview ZIP must be extracted as a whole before running its executable; it does not use the installer's in-app update flow.
- `SHA256SUMS-installers-...` checks the installer packages for that edition and platform. `SHA256SUMS-electron-...` checks a preview; `SHA256SUMS-browser.txt` checks the browser archive. A checksum verifies that your download matches the published bytes; it does not establish publisher identity.
- Update-feed files and the installers they name must stay together on the release. Removing or renaming either can break in-app updates.

## Testing the Windows updater fix

Version **1.9.2** changes **Restart and install** to apply an approved update silently in the existing installation and reopen the app. Saving work and explicit download/restart approval are still required.

When updating an older installed version to 1.9.2, the older app still controls that first installer handoff: you may need to finish the wizard and reopen the app manually once. To test the corrected handoff, install 1.9.2 and then update to a later published version. Installing 1.9.2 alone does not test an update initiated by 1.9.2.
