/* eslint-disable @next/next/no-img-element -- authentic local product captures are intentionally served without an optimizer */
import Link from "next/link";
import CalculatorCards from "./CalculatorCards";
import OutputShowcase from "./OutputShowcase";
import SiteHeader from "./SiteHeader";
import SiteFooter from "./SiteFooter";

export default function Home() {
  return (
    <main className="platform-shell">
      <SiteHeader showGithub={false} />
      <section className="platform-hero" id="top">
        <div className="platform-hero-copy">
          <p className="marketing-eyebrow"><span /> Roadway engineering software</p>
          <h1>Roadway software<br /><em>you can verify.</em></h1>
          <p>VeriCivil makes focused software for roadway engineers and inspectors: browser-based engineering tools and RoadStation for iPhone. Each tool keeps its assumptions and limits in view.</p>
          <div className="hero-actions"><a className="marketing-button primary-action" href="/roadstation">Explore RoadStation <span>→</span></a><a className="marketing-button secondary-action" href="/calculators">Browse engineering tools <span>↗</span></a></div>
          <div className="hero-trust"><span><i /> Files stay local</span><span><i /> Methods stay visible</span><span><i /> Engineering review required</span></div>
        </div>
        <div className="platform-hero-showcase" aria-label="Authentic Superelevation Calculator views">
          <a className="hero-capture hero-capture-main" href="/calculators/superelevation">
            <div><img src="/showcase/calculator-ui.png" alt="Superelevation browser workspace with curve inputs, calculated results, lane diagram, and export controls" width="1425" height="1626" /></div>
            <span><b>Live browser workspace</b><small>LandXML · calculations · exports</small></span>
          </a>
          <div className="hero-capture-row">
            <figure className="hero-capture"><div><img src="/showcase/lane-profile-diagram.png" alt="Expanded station-aware superelevation lane profile" width="1440" height="1200" /></div><figcaption>Lane profiles</figcaption></figure>
            <figure className="hero-capture"><div><img src="/showcase/dxf-plan-view.png" alt="Superelevation plan view for SR 82 with alignment, slope, and station callouts" width="2880" height="1376" /></div><figcaption>Overlay DXF</figcaption></figure>
          </div>
        </div>
      </section>

      <section className="platform-signal-strip" aria-label="VeriCivil product principles"><div><span>LOCAL</span><strong>Project files stay on device</strong></div><i>→</i><div><span>VISIBLE</span><strong>Assumptions and provenance</strong></div><i>→</i><div><span>TESTED</span><strong>Tested engineering logic</strong></div></section>

      <section className="platform-product" id="products">
        <div className="platform-product-copy">
          <p className="marketing-eyebrow"><span /> VeriCivil products</p>
          <h2>RoadStation.<br /><em>Alignment context on iPhone.</em></h2>
          <p>RoadStation by VeriCivil helps roadway engineers and inspectors read approximate station and LT/RT offset from supported LandXML alignments. Confirm the project CRS and units, then see the alignment in MapKit context.</p>
          <p className="platform-product-caveat">Phone GPS is approximate and is not survey-grade.</p>
          <Link className="marketing-button secondary-action" href="/roadstation">Explore RoadStation <span>↗</span></Link>
        </div>
        <Link className="platform-product-image" href="/roadstation" aria-label="Explore RoadStation for iPhone">
          <img src="/roadstation/inspection.webp" alt="RoadStation manual inspection of a fictional alignment, showing a MapKit view and station 100+50.00 at 5.000 feet right" width="1170" height="2532" />
          <span>Fictional sample · manual query</span>
        </Link>
      </section>

      <section className="platform-calculators" id="calculators">
        <div className="section-intro"><p className="marketing-eyebrow"><span /> Available calculators</p><h2>One toolkit.<br />A flagship workspace and focused utilities.</h2><p>Superelevation is VeriCivil’s professional design workspace. Supporting tools stay fast, focused, and free where noted.</p></div>
        <CalculatorCards />
      </section>

      <section className="platform-featured">
        <div className="platform-featured-copy"><p className="marketing-eyebrow"><span /> Featured professional workflow</p><h2>Superelevation from curve input to design review.</h2><p>The original VeriCivil application remains the professional workspace for roadway transitions, LandXML corridors, lane-by-lane QA, and CAD-ready exports.</p><a className="marketing-button secondary-action" href="/calculators/superelevation">Explore Superelevation <span>↗</span></a></div>
        <OutputShowcase />
      </section>

      <section className="platform-principles">
        <div className="section-intro"><p className="marketing-eyebrow"><span /> Built for verification</p><h2>Useful results need visible context.</h2></div>
        <div className="principle-grid"><article><span>01</span><h3>Traceable methods</h3><p>Formulas, assumptions, units, source revisions, and engine versions stay connected to results.</p></article><article><span>02</span><h3>Local processing</h3><p>Browser calculations run on your device. RoadStation keeps imported alignments and saved projects on your iPhone.</p></article><article><span>03</span><h3>Focused tools</h3><p>From design exports to field station and offset, each product focuses on a practical roadway task.</p></article></div>
      </section>

      <section className="platform-account-callout"><div><p className="marketing-eyebrow"><span /> Superelevation Pro</p><h2>Professional project workflows remain available.</h2><p>Manage Superelevation Pro for LandXML, multi-curve projects, supported DOT profiles, PDF, ORD CSV, and overlay DXF exports.</p></div><a className="marketing-button primary-action" href="/account">Manage Superelevation Pro <span>↗</span></a></section>

      <section className="engineering-note"><span>ENGINEERING AIDS</span><p>The licensed professional responsible for the project must independently verify criteria, inputs, assumptions, stationing, coordinate systems, results, quantities, and deliverables.</p></section>
      <SiteFooter />
    </main>
  );
}
