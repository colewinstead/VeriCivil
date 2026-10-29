# SignPath onboarding

Status: October 28, 2026. Application/approval pending; no SignPath credentials, project, certificate, or signing policy is configured. This document and the review workflow prepare the application; they do not establish eligibility or production signing.

## Public application resources

- Homepage: https://vericivil.com
- Downloads: https://vericivil.com/downloads
- Code signing policy and desktop privacy: https://vericivil.com/code-signing
- Repository: https://github.com/colewinstead/VeriCivil
- Current code license: MIT. No license change is needed just to apply.
- Proposed author/committer/reviewer/signing approver: Cole Winstead (`colewinstead`). This is a single-maintainer project, not independent review. Confirm the roles with SignPath during onboarding.

Publish the policy through the normal tested main/release/Site process before replacing the application's download URL with `/downloads`. The application should say: "Current automated releases are unsigned. A pending-status code signing policy is published at https://vericivil.com/code-signing. The protected GitHub Actions signing-review workflow is prepared; activation requires SignPath approval and organization/project configuration. AASHTO-derived data redistribution clearance remains unresolved as documented in the repository."

Do not claim approval, successful signing, or rights clearance. Once approved and working, update the pending status and activate the required attribution: "Free code signing provided by SignPath.io, certificate by SignPath Foundation" with links to both providers. Keep the policy linked from the homepage, downloads, and release pages. SignPath does not supply Apple Developer signing/notarization.

## After approval

1. Resolve the [AASHTO rights record](AASHTO_2018.md#sources-and-rights) and confirm full-package eligibility with SignPath. A grant limited to this maintainer or forbidding downstream redistribution may be incompatible with an open-source package. See the [permissions request draft](aashto-permission-request.md).
2. Enable/confirm MFA on the maintainer's GitHub and SignPath accounts. Preserve the existing main protections and the owner-approved `desktop-production` environment restricted to main.
3. Follow [SignPath's GitHub integration instructions](https://docs.signpath.io/trusted-build-systems/github). Installing its GitHub App/granting repository access is an onboarding action for the owner to review; this change does not grant that access.
4. Create/link the project to GitHub.com as a Trusted Build System. Configure a signing policy requiring manual approval; do not use an automatic release approval policy.
5. Have SignPath review an artifact configuration for the GitHub-uploaded ZIP containing exactly `VeriCivilSuperelevation.exe` and `installer.exe`. Enforce product name `VeriCivil Superelevation`, matching product versions, expected paths, and timestamped Authenticode signing. Do not sign third-party Electron executables or DLLs under this project's certificate. The installer here is an **outer-container signing test**: its embedded app and uninstaller remain unsigned.
6. In the protected `desktop-production` GitHub environment, add the secret `SIGNPATH_API_TOKEN` (minimum permissions needed for this project/policy). Add environment variables `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_SIGNING_POLICY_SLUG`, `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG`, and `SIGNPATH_PUBLISHER` using values confirmed by SignPath. `SIGNPATH_PUBLISHER` is the certificate's exact Windows publisher/common name, not the maintainer's name. Do not paste tokens into chat or commit them.
7. Only after those checks, set environment variable `SIGNPATH_ENABLED=true`. Until then the workflow fails closed before building or requesting signing. Do not invent placeholder credentials or enable this flag before approval.
8. Run **Windows SignPath Review** from main with the latest published stable tag. Approve the GitHub environment and each signing request manually. The workflow rebuilds that released source on GitHub-hosted runners, runs engine/desktop/offline checks, uploads the input as a GitHub artifact, submits its artifact ID through the pinned official SignPath action, verifies both returned signatures/publisher/timestamps, and saves review artifacts/checksums for seven days.

No release assets or update feeds are published by this workflow. It has read-only repository permissions. A failed or rejected signing request must not fall back to unsigned publication.

## Production gates remaining

The review workflow deliberately does not set `VERICIVIL_SIGNED_RELEASE`, rename the installer as a production release, or enable signed updates. Signing an installer after packaging cannot sign the app inside it. Before integrating SignPath into **Signed Desktop Release**, confirm with SignPath an Electron/NSIS-compatible sequence that signs the app before packaging and signs the uninstaller and final installer at the appropriate stages. Verify the installed app, installer, and uninstaller with Windows trust checks, and run signed N-to-N+1 upgrades plus tampered-package rejection.

Generate blockmaps, sizes, hashes, and update metadata from the final signed bytes only. Confirm electron-updater trusts the approved publisher. Publish binaries before update metadata. Windows signing must be releasable independently of missing Mac credentials; Mac signature/notarization acceptance remains a separate gate. The existing certificate-based production workflow is unchanged and still requires its own Windows and Apple credentials.

References: [Foundation conditions](https://signpath.org/terms.html), [official GitHub integration](https://docs.signpath.io/trusted-build-systems/github), [Electron Windows signing](https://www.electron.build/docs/features/code-signing/code-signing-win/).
