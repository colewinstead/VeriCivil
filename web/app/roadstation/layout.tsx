import type { Metadata } from "next";
import Link from "next/link";
import SiteHeader from "../SiteHeader";
import SiteFooter from "../SiteFooter";

export const metadata: Metadata = {
  title: "RoadStation for iPhone",
  description: "RoadStation by VeriCivil helps roadway engineers and inspectors read approximate station and LT/RT offset from supported LandXML alignments on iPhone.",
  openGraph: {
    type: "website",
    title: "RoadStation by VeriCivil",
    description: "LandXML alignment context, explicit CRS, and approximate station and offset on iPhone.",
    images: [{ url: "/roadstation/og.png", width: 1200, height: 630, alt: "RoadStation by VeriCivil, showing a fictional alignment in the iPhone app" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "RoadStation by VeriCivil",
    description: "LandXML alignment context and approximate station and offset on iPhone.",
    images: ["/roadstation/og.png"],
  },
};

export default function RoadStationLayout({ children }: { children: React.ReactNode }) {
  return <div className="marketing-shell roadstation-shell">
    <SiteHeader compact showGithub={false} />
    <main>
      <nav className="roadstation-nav" aria-label="RoadStation navigation"><Link href="/roadstation">RoadStation <span>by VeriCivil</span></Link><div><Link href="/roadstation/support">Support & sample</Link><Link href="/roadstation/privacy">Privacy</Link></div></nav>
      {children}
    </main>
    <SiteFooter />
  </div>;
}
