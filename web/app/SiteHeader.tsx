import Link from "next/link";

export default function SiteHeader({ compact = false, showGithub = true }: { compact?: boolean; showGithub?: boolean }) {
  return (
    <nav className={`platform-nav${compact ? " compact" : ""}`} aria-label="Primary navigation">
      <Link className="platform-brand" href="/" aria-label="VeriCivil home">
        <span className="platform-brand-mark">VC</span>
        <span><strong>VeriCivil</strong><small>Roadway engineering tools</small></span>
      </Link>
      <div className="platform-nav-links">
        <Link className="nav-calculators" href="/calculators">Calculators</Link>
        <Link href="/calculators/superelevation">Superelevation</Link>
        <Link className="nav-roadstation" href="/roadstation">RoadStation</Link>
        <Link href="/account">Account</Link>
        {showGithub && <a href="https://github.com/colewinstead/VeriCivil">GitHub</a>}
      </div>
      <Link className="nav-cta" href="/calculators">Browse tools <span>↗</span></Link>
    </nav>
  );
}
