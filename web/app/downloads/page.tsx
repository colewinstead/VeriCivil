import type { Metadata } from "next";
import Link from "next/link";
import SiteHeader from "../SiteHeader";
import SiteFooter from "../SiteFooter";
import { DESKTOP_RELEASES, latestDesktopDownloads } from "../../lib/desktop-downloads";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Desktop downloads", description: "Download VeriCivil Superelevation for Windows or Mac. Calculations run locally with a bundled offline engine.", alternates: { canonical: "https://vericivil.com/downloads" } };

export default async function Downloads() {
  const release = await latestDesktopDownloads();
  return <main className="platform-shell">
    <SiteHeader />
    <section className="desktop-downloads">
      <p className="marketing-eyebrow">VeriCivil Superelevation</p>
      <h1>Your engineering workspace.<br />On your computer.</h1>
      <p className="downloads-lede">Work with local projects, LandXML, reports, and design exports using the bundled offline calculation engine. Current desktop tools are free; no account is required.</p>
      <p>{release ? `Latest release: ${release.version}` : "The release list is temporarily unavailable. GitHub has the latest available files."}</p>
      <div className="desktop-download-list">
        {release?.downloads.map(item => <article key={item.label}>
          <h2>{item.label}</h2>
          <p>{item.unsigned ? "Unsigned evaluation build" : "Signed desktop release"} · {item.portable ? "Portable ZIP" : item.filename.endsWith(".exe") ? "Windows installer" : "Mac disk image"}</p>
          <a className="marketing-button primary-action" href={item.url}>Download for {item.label}</a>
          <p>{item.portable ? "Extract the entire ZIP before opening the application." : item.filename.endsWith(".exe") ? "Run the installer, then open VeriCivil from the Start menu." : "Open the disk image and copy the app to Applications."}</p>
          {item.unsigned && <p>Signing is not configured for this build. Automatic installation of updates is disabled.</p>}
        </article>)}
      </div>
      <a className="marketing-button secondary-action" href={DESKTOP_RELEASES}>All release files, notes, and checksums</a>
      <section className="downloads-notes"><h2>Code signing policy</h2><p>SignPath Foundation approval is pending. Current automated desktop releases are unsigned; automatic installation of updates remains disabled. Read the <Link href="/code-signing">Code signing policy</Link> for signing status, release approval, and desktop privacy details.</p></section>
      <section className="downloads-notes"><h2>Before you start</h2><p>Keep a separate backup of your project files. Review the release notes and independently verify engineering criteria, inputs, calculations, and deliverables.</p><p>Updates and downloads need an internet connection. Engineering calculations run locally. The app keeps local recovery snapshots and support logs; diagnostic reports are exported only when you choose.</p><p>Prefer the browser? <Link href="/calculators/superelevation">Open Superelevation online</Link>.</p></section>
    </section>
    <SiteFooter />
  </main>;
}
