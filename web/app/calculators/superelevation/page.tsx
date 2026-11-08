import type { Metadata } from "next";
import CalculatorApp from "../../CalculatorApp";

export const metadata: Metadata = {
  alternates: { canonical: "https://vericivil.com/calculators/superelevation" },
  title: "Superelevation Calculator",
  description: "Calculate roadway superelevation, runoff, tangent runout, and lane slopes from curve inputs. Try a free worked example without an account.",
};

export default function SuperelevationCalculatorPage() {
  return (
    <CalculatorApp intro={
      <div className="superelevation-intro">
        <p>Calculate roadway superelevation transitions from the curve radius, design speed, and start station (PC). Review the design rate, runoff and tangent runout lengths, transition stations, and signed lane slopes.</p>
        <p><strong>Free manual calculations require no account.</strong> Start with Mississippi DOT criteria. Pro adds the Tennessee DOT profile, LandXML import, PDF reports, OpenRoads Designer CSV, and overlay DXF exports.</p>
        <details>
          <summary>Worked example for a 45 mph rural curve</summary>
          <p>Under <strong>Project</strong>, choose <strong>Load synthetic sample</strong> on the Free plan. It fills in a 2,000 ft radius, a left turn starting at station 100+00, and a two-lane section that rotates about the centerline.</p>
          <p>In <strong>Results</strong>, the design rate is <strong>4.8%</strong>, with <strong>107 ft of runoff</strong> and <strong>44 ft of tangent runout</strong>. Under Lane events, full superelevation begins at <strong>100+32.10</strong>. The entry places 30% of the 107 ft runoff after the PC, or 32.10 ft.</p>
          <figure>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/showcase/superelevation-sample-results.webp" width={522} height={86} loading="lazy" alt="Calculator Results panel showing a rate of 0.0480, runoff of 107 ft, and tangent runout of 44 ft." />
            <figcaption>Results from the synthetic curve. Criteria source: <a href="https://mdot.ms.gov/documents/Roadway%20Design/Standards/Drawings/Roadway%20Design%20Standard%20Drawings.pdf">Mississippi DOT standard drawings SE-2A and SE-3A</a>.</figcaption>
          </figure>
        </details>
      </div>
    } />
  );
}
