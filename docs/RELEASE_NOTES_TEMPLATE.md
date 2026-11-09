## Download the desktop app

Choose **one installer** for your computer. Existing users should keep the same edition.

| Computer | VeriCivil edition | Neutral edition (no VeriCivil branding) |
| --- | --- | --- |
| Windows x64 | [Windows installer](https://github.com/colewinstead/VeriCivil/releases/download/{{TAG}}/VeriCivil-Superelevation-{{VERSION}}-win-x64-unsigned.exe) | [Windows installer](https://github.com/colewinstead/VeriCivil/releases/download/{{TAG}}/Superelevation-Calculator-{{VERSION}}-win-x64-unsigned.exe) |
| Mac: Apple Silicon | [Mac disk image](https://github.com/colewinstead/VeriCivil/releases/download/{{TAG}}/VeriCivil-Superelevation-{{VERSION}}-mac-arm64-unsigned.dmg) | [Mac disk image](https://github.com/colewinstead/VeriCivil/releases/download/{{TAG}}/Superelevation-Calculator-{{VERSION}}-mac-arm64-unsigned.dmg) |
| Mac: Intel | [Mac disk image](https://github.com/colewinstead/VeriCivil/releases/download/{{TAG}}/VeriCivil-Superelevation-{{VERSION}}-mac-x64-unsigned.dmg) | [Mac disk image](https://github.com/colewinstead/VeriCivil/releases/download/{{TAG}}/Superelevation-Calculator-{{VERSION}}-mac-x64-unsigned.dmg) |

**Why so many assets?** Most users can ignore the preview packages, alternative Mac ZIPs, browser build, and source archives. `SHA256SUMS-*.txt` files verify downloads; `.yml` files support Windows updates. [Read the download guide and full asset breakdown](https://github.com/colewinstead/VeriCivil/blob/{{TAG}}/docs/RELEASE_ASSETS.md).

**Unsigned evaluation builds.** SignPath approval is pending. Windows installers support user-approved updates without publisher-signature verification; unsigned Mac and portable builds require manual updates. [Code signing policy](https://vericivil.com/code-signing).
