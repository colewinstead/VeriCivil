import Link from "next/link";

export default function SiteFooter() {
  return <footer className="platform-footer">
    <Link className="platform-brand" href="/"><span className="platform-brand-mark">VC</span><span><strong>VeriCivil</strong><small>Roadway engineering tools</small></span></Link>
    <p>Focused tools with visible engineering context.</p>
    <div><Link href="/roadstation">RoadStation</Link><Link href="/calculators">Calculators</Link><Link href="/account">Account</Link><Link href="/terms">Terms</Link><Link href="/privacy">Privacy</Link></div>
  </footer>;
}
