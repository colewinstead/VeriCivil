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
      <header><p>VeriCivil Superelevation desktop</p><h1>Code signing policy</h1><span>Updated November 9, 2026</span></header>
      <section><h2>Current status: unsigned Windows builds</h2>
        <p>Desktop releases currently focus on Windows x64. Windows installers and portable previews are unsigned evaluation builds. Code signing work and Mac desktop builds are paused.</p>
        <p>Windows installers support update downloads and restarts with your approval. Updates use HTTPS and checksums without publisher-signature verification. Portable builds require manual replacement. Windows may show an unknown-publisher or SmartScreen warning; review the release source and checksums before deciding whether to install.</p>
        <p>Older Mac downloads may remain in GitHub release history, but new Mac desktop builds are not being published. Check the status shown beside each <Link href="/downloads">Windows download</Link>.</p>
      </section>
      <section><h2>Release responsibilities</h2>
        <p>Author, committer, and reviewer: <a href="https://github.com/colewinstead">Cole Winstead</a>. Contributions from other authors require review before merging. The maintainer currently holds all these roles; this does not represent independent review.</p>
        <p>Release builds run from main-branch source on GitHub-hosted runners after required checks pass. Pull-request builds produce review artifacts only. Windows installers, update feeds, portable previews, and checksums are published through GitHub Releases.</p>
      </section>
      <section id="desktop-privacy"><h2>Desktop privacy and network access</h2>
        <p>Engineering calculations, imported LandXML, projects, recovery snapshots, recent-file paths, and exports stay on your computer. The desktop app has no account sign-in, billing, product analytics, or remote LandXML retention. Support logs stay local; Export diagnostics writes a local file that you may choose to share.</p>
        <p>Packaged apps automatically check GitHub Releases for updates at startup and periodically while running. You can also check manually. These requests disclose normal connection information, such as your IP address, to GitHub. Downloads and approved Windows update downloads use GitHub and its delivery services; update download and restart require your action. Calculations work offline.</p>
        <p>Opening a website from the app uses your browser and that website&apos;s privacy practices. See <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub&apos;s privacy statement</a> and the <Link href="/privacy">VeriCivil website privacy policy</Link>. The browser service has separate analytics and optional file-retention behavior described there.</p>
      </section>
      <section><h2>License and engineering review</h2>
        <p>Project code is MIT-licensed. Redistribution clearance for embedded AASHTO-derived data remains unresolved in the <a href="https://github.com/colewinstead/VeriCivil/blob/main/docs/AASHTO_2018.md">AASHTO source and rights record</a>. Desktop distribution does not grant third-party content rights or establish engineering accuracy.</p>
        <p>The responsible engineering professional must independently verify criteria, inputs, calculations, and deliverables. Release checksums help detect changed downloads; they do not establish publisher identity or engineering certification.</p>
      </section>
    </article>
    <SiteFooter />
  </main>;
}
