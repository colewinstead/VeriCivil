/* eslint-disable @next/next/no-img-element -- fixed local showcase captures do not use an image optimization service */
"use client";

import { useEffect, useState } from "react";

type Preview = {
  type: "image" | "pdf";
  src: string;
  thumbnail: string;
  alt: string;
  eyebrow: string;
  title: string;
  width: number;
  height: number;
};

const previews: Preview[] = [
  {
    type: "image",
    src: "/showcase/lane-profile-diagram.png",
    thumbnail: "/showcase/lane-profile-diagram.png",
    alt: "Expanded browser diagram showing left and right lane superelevation profiles for the SR 9 corridor",
    eyebrow: "Lane diagram",
    title: "Station-aware profiles",
    width: 2048,
    height: 1024,
  },
  {
    type: "image",
    src: "/showcase/dxf-plan-view.png",
    thumbnail: "/showcase/dxf-plan-view.png",
    alt: "Superelevation plan view for SR 82 showing the alignment and signed slope and station callouts",
    eyebrow: "Overlay DXF",
    title: "Transition callouts",
    width: 2880,
    height: 1376,
  },
  {
    type: "pdf",
    src: "/showcase/superelevation-report-sample.pdf",
    thumbnail: "/showcase/pdf-report.png",
    alt: "First page of the generated three-page superelevation calculation PDF report",
    eyebrow: "PDF report",
    title: "3-page design record",
    width: 1224,
    height: 1584,
  },
];

export default function OutputShowcase() {
  const [active, setActive] = useState<Preview | null>(null);

  useEffect(() => {
    if (!active) return;

    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActive(null);
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [active]);

  return (
    <div className="output-showcase" aria-label="Real Superelevation Calculator outputs">
      <a className="output-card output-card-ui" href="/calculators/superelevation">
        <figure>
          <div className="output-image output-image-ui">
            <img src="/showcase/calculator-ui.png" alt="Browser calculator showing the SR 82 project, curve inputs, calculated results, lane diagram, and export controls" width="1425" height="1626" />
          </div>
          <figcaption><span>Browser UI</span><strong>Calculate and review</strong><small>Open the live workspace ↗</small></figcaption>
        </figure>
      </a>

      {previews.map((preview) => (
        <button
          className="output-card output-card-button"
          type="button"
          key={preview.src}
          aria-haspopup="dialog"
          onClick={() => setActive(preview)}
        >
          <figure>
            <div className={`output-image output-image-${preview.type === "pdf" ? "pdf" : preview.eyebrow === "Overlay DXF" ? "dxf" : "diagram"}`}>
              <img src={preview.thumbnail} alt={preview.alt} width={preview.width} height={preview.height} />
            </div>
            <figcaption><span>{preview.eyebrow}</span><strong>{preview.title}</strong><small>Open preview ↗</small></figcaption>
          </figure>
        </button>
      ))}

      {active && (
        <div className="output-popup-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setActive(null);
        }}>
          <section className={`output-popup output-popup-${active.type}`} role="dialog" aria-modal="true" aria-labelledby="output-popup-title">
            <header>
              <div><span>{active.eyebrow}</span><h2 id="output-popup-title">{active.title}</h2></div>
              <button type="button" className="output-popup-close" onClick={() => setActive(null)} autoFocus aria-label="Close preview">Close ×</button>
            </header>
            {active.type === "pdf"
              ? <iframe src={active.src} title="Sample superelevation PDF report" />
              : <img src={active.src} alt={active.alt} width={active.width} height={active.height} />}
          </section>
        </div>
      )}
    </div>
  );
}
