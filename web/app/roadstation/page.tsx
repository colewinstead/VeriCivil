/* eslint-disable @next/next/no-img-element -- authentic local product captures are served without an optimizer */
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  alternates: { canonical: "https://vericivil.com/roadstation" },
};

export default function RoadStationPage() {
  return <article className="roadstation-page">
    <header className="roadstation-hero">
      <div className="roadstation-hero-copy">
        <p className="marketing-eyebrow"><span /> RoadStation by VeriCivil · iPhone</p>
        <h1>Find your station.<br /><em>Understand your offset.</em></h1>
        <p className="roadstation-lead">Bring a supported LandXML roadway alignment to your iPhone. RoadStation gives engineers and inspectors approximate station and LT/RT offset with the project coordinate system and phone positioning quality in view.</p>
        <div className="hero-actions"><Link className="marketing-button primary-action" href="/roadstation/support">Explore the synthetic sample <span>↗</span></Link><a className="marketing-button secondary-action" href="#workflow">See how it works <span>↓</span></a></div>
        <p className="roadstation-availability">App Store release in preparation · iOS 17 or later</p>
      </div>
      <figure className="roadstation-hero-image"><img src="/roadstation/inspection.webp" alt="RoadStation Inspect Alignment screen showing a fictional alignment on a MapKit satellite map and a manual query at STA 100+50.00, 5.000 feet right" width="1170" height="2532" /><figcaption>Fictional example · manual query, not a live GPS reading</figcaption></figure>
    </header>

    <section className="roadstation-workflow" id="workflow">
      <div className="roadstation-section-intro"><p className="marketing-eyebrow"><span /> Field workflow</p><h2>From project file to field context.</h2><p>RoadStation works from the alignment you supply and the CRS and units you confirm.</p></div>
      <ol>
        <li><span>01</span><h3>Import LandXML</h3><p>Choose a supported .xml or .landxml alignment file from iOS Files.</p></li>
        <li><span>02</span><h3>Confirm CRS & units</h3><p>Check the project EPSG code, datum and exact units against your documentation. RoadStation does not confirm a suggested CRS for you.</p></li>
        <li><span>03</span><h3>Select an alignment</h3><p>Choose the alignment to inspect. Saved projects reopen on your device for return visits.</p></li>
        <li><span>04</span><h3>Read station & offset</h3><p>Field Position uses foreground phone location for an approximate horizontal station and LT/RT offset. Accuracy and stale-position status remain visible.</p></li>
      </ol>
    </section>

    <section className="roadstation-gallery" aria-labelledby="roadstation-gallery-title">
      <div className="roadstation-section-intro"><p className="marketing-eyebrow"><span /> Inside the app</p><h2 id="roadstation-gallery-title">Your alignment, with the context to use it.</h2><p>MapKit satellite or street maps show geographic context where available. Engineering View shows the local alignment when map imagery is unavailable. Map drawing does not determine the station or offset.</p></div>
      <div className="roadstation-gallery-grid">
        <figure><img src="/roadstation/projects.webp" alt="RoadStation Projects screen showing a saved fictional LandXML project" width="1170" height="2532" loading="lazy" /><figcaption><strong>Return to a project</strong><span>Saved LandXML source, alignment and confirmed CRS remain on device.</span></figcaption></figure>
        <figure><img src="/roadstation/crs.webp" alt="RoadStation project screen showing explicit EPSG:6507 and US survey foot confirmation" width="1170" height="2532" loading="lazy" /><figcaption><strong>Know the coordinate system</strong><span>Confirm the project CRS and exact units before field positioning.</span></figcaption></figure>
        <figure><img src="/roadstation/field-position.webp" alt="RoadStation Field Position screen showing the fictional alignment on a MapKit map and a location permission denied warning, with no station or offset result" width="1170" height="2532" loading="lazy" /><figcaption><strong>See positioning status</strong><span>This capture shows permission denied, so no GPS station or offset is displayed.</span></figcaption></figure>
      </div>
      <p className="roadstation-gallery-note">Screens use a fictional sample, not a surveyed roadway or live field accuracy example.</p>
    </section>

    <section className="roadstation-caution" aria-labelledby="roadstation-caution-title"><span>POSITIONING LIMITS</span><div><h2 id="roadstation-caution-title">Phone GPS is approximate and not survey-grade.</h2><p>Check location accuracy and freshness, project control, CRS and units before interpreting a result. Stale or invalid fixes do not create a new calculation. Map imagery is context, not a surveyed control point. RoadStation does not replace survey equipment or professional judgment.</p></div></section>

    <section className="roadstation-demo" aria-labelledby="roadstation-demo-title"><div><p className="marketing-eyebrow"><span /> Product walkthrough</p><h2 id="roadstation-demo-title">See the workflow in motion.</h2><p>A short demo video is being prepared. Until it is ready, use the fictional sample and worked manual check to explore import, CRS confirmation and station/offset.</p><Link className="marketing-button secondary-action" href="/roadstation/support">View sample & worked check <span>↗</span></Link></div><div className="roadstation-demo-frame" role="img" aria-label="Reserved space for the RoadStation demo video"><span>RoadStation demo video</span><strong>Coming before launch</strong></div></section>

    <section className="roadstation-launch"><div><p className="marketing-eyebrow"><span /> Availability</p><h2>Built for the next site visit.</h2><p>RoadStation is being prepared for App Store release. The verified App Store link will appear here when available. No app account or subscription is required.</p><p className="roadstation-requirements">Requires iPhone with iOS 17 or later, a supported LandXML alignment, and a documented coordinate system. Location permission is needed for live Field Position; manual inspection works without it.</p></div><div className="roadstation-launch-links"><Link className="marketing-button primary-action" href="/roadstation/support">Explore the synthetic sample <span>↗</span></Link><Link href="/roadstation/privacy">Read RoadStation privacy</Link></div></section>
  </article>;
}
