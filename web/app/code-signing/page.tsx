import type { Metadata } from "next";
import Link from "next/link";
import SiteHeader from "../SiteHeader";
import SiteFooter from "../SiteFooter";

export const metadata: Metadata = {
  title: "Code signing policy",
  description: "VeriCivil desktop signing status, release responsibilities, and privacy information.",
  alternates: { canonical: "https://vericivil.com/code-signing" },
};

export default function CodeSigningPolicy() {
  return <main className="platform-shell">
    <SiteHeader />
    <article className="legal-document">
      <header><p>VeriCivil Superelevation desktop</p><h1>Code signing policy</h1><span>Updated October 28, 2026</span></header>
      <section><h2>Current status: approval pending</h2>
        <p>We are applying to the SignPath Foundation for Windows code signing. Approval is pending; SignPath signing is not active. Current automated Windows and Mac releases are unsigned evaluation builds, and automatic installation of updates is disabled.</p>
        <p>If approved and activated, Windows signing will be described as: Free code signing provided by <a href="https://signpath.io">SignPath.io</a>, certificate by <a href="https://signpath.org">SignPath Foundation</a>. This is planned attribution, not a claim that current downloads are signed or endorsed by SignPath.</p>
        <p>Mac signing and notarization require a separate Apple Developer identity and are not configured. Check the status shown beside each <Link href="/downloads">desktop download</Link>.</p>
      </section>
      <section><h2>Release responsibilities</h2>
        <p>Author, committer, reviewer, and proposed signing approver: <a href="https://github.com/colewinstead">Cole Winstead</a>. Contributions from other authors require review before merging. The maintainer currently holds all these roles; this does not represent independent review.</p>
        <p>Signing requires manual release approval. Production requests are restricted to released main-branch source built on GitHub-hosted runners. Signing credentials belong in the protected desktop-production environment, outside the repository and pull-request jobs. Multi-factor authentication is required for GitHub and SignPath signing participants before activation.</p>
        <p>The prepared SignPath workflow produces review artifacts only. Signing the outer Windows installer does not sign its embedded application or uninstaller. Production publication and update feeds remain blocked until that packaging path and installed upgrades have been verified.</p>
      </section>
      <section id="desktop-privacy"><h2>Desktop privacy and network access</h2>
        <p>Engineering calculations, imported LandXML, projects, recovery snapshots, recent-file paths, and exports stay on your computer. The desktop app has no account sign-in, billing, product analytics, or remote LandXML retention. Support logs stay local; Export diagnostics writes a local file that you may choose to share.</p>
        <p>Packaged apps automatically check GitHub Releases for updates at startup and periodically while running. You can also check manually. These requests disclose normal connection information, such as your IP address, to GitHub. Downloads and approved signed-build update downloads use GitHub and its delivery services; update download and restart require your action. Calculations work offline.</p>
        <p>Opening a website from the app uses your browser and that website&apos;s privacy practices. See <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub&apos;s privacy statement</a> and the <Link href="/privacy">VeriCivil website privacy policy</Link>. The browser service has separate analytics and optional file-retention behavior described there.</p>
      </section>
      <section><h2>License and engineering review</h2>
        <p>Project code is MIT-licensed. Redistribution clearance for embedded AASHTO-derived data remains unresolved in the <a href="https://github.com/colewinstead/VeriCivil/blob/main/docs/AASHTO_2018.md">AASHTO source and rights record</a>. Signing approval does not grant third-party content rights or establish engineering accuracy.</p>
        <p>The responsible engineering professional must independently verify criteria, inputs, calculations, and deliverables. A signature identifies a publisher and protects artifact integrity; it is not engineering certification.</p>
      </section>
    </article>
    <SiteFooter />
  </main>;
}
