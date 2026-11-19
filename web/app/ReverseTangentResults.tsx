"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
type Dict = Record<string, any>;

export default function ReverseTangentResults({ result }: { result: Dict | null }) {
  if (!result) return <div className="results-empty"><h3>Ready to check reverse-curve tangent</h3><p>Enter two radii, design speed and roadway settings. No stations are needed. AASHTO also requires project placement.</p></div>;
  return <div aria-live="polite">
    <div className="metric-grid"><article style={{gridColumn:"1 / -1"}}><span>Minimum tangent for superelevation transitions</span><strong>{Number(result.independent_tangent_ft).toFixed(2)} ft</strong><small>Return to the initial tangent section; no extra hold</small></article></div>
    {result.governing_carriageway !== "roadway" && <p className="helper">Controlling carriageway: {result.governing_carriageway}. {Object.entries(result.carriageway_demands_ft).map(([side, demand]) => `${side}: ${Number(demand).toFixed(2)} ft`).join(" · ")}</p>}
    {result.mdot_linked_tangent_ft != null && <section className="result-warning"><strong>MDOT linked reversal — project-specific rule: {Number(result.mdot_linked_tangent_ft).toFixed(2)} ft</strong><p>Uses 0.7Lr₁ + 0.7Lr₂ and omits intervening runouts. This is the calculator’s existing project rule, not a published MDOT reverse-curve minimum. Actual alignment coordination and project applicability require review.</p></section>}
    <div className="lane-tables"><div style={{gridColumn:"1 / -1",overflowX:"auto"}}><h4>Curve transition breakdown</h4><table><thead><tr><th>Curve / roadway</th><th>Design radius (ft)</th><th>Curve cross slope</th><th>Runoff Lr (ft)</th><th>Runout Lt (ft)</th><th>Tangent demand (ft)</th></tr></thead><tbody>
      {result.curves.flatMap((curve: Dict, index: number) => Object.entries(curve.carriageways || {roadway: curve}).map(([side, raw]) => {
        const child = raw as Dict;
        return <tr key={`${index}-${side}`}><th scope="row">{index + 1} · {curve.curve_direction}{side !== "roadway" ? ` · ${side}` : ""}</th><td>{Number(child.radius_provenance?.design_radius_ft ?? curve.radius_ft).toFixed(2)}</td><td>{child.section_transition?.target_slope_label || `${(Number(child.e) * 100).toFixed(2)}%`}</td><td>{Number(child.Lr).toFixed(2)}</td><td>{Number(child.Lt).toFixed(2)}</td><td>{Number(child.tangent_demand_ft).toFixed(2)}</td></tr>;
      }))}
    </tbody></table></div></div>
    <p className="helper">{result.scope_note}</p>
    <p className="helper"><strong>Overall agency minimum: not established. Signing: not evaluated.</strong> A zero transition demand does not establish a zero geometric minimum.</p>
    {result.curves.map((curve: Dict, index: number) => <details className="criteria-reference" key={index}><summary>Curve {index + 1} calculation sources</summary>
      {Object.entries(curve.carriageways || {roadway: curve}).map(([side, raw]) => {
        const child = raw as Dict;
        const sources = child.calculation_metadata.calculation_sources || child.calculation_metadata.criteria.calculation_sources || [];
        return <div key={side}>{side !== "roadway" && <h4>{side} carriageway</h4>}<ul>{sources.map((source: Dict, n: number) => <li key={n}><span>{source.component}</span><b>{source.reference}</b><em>{String(source.mode).replaceAll("_", " ")}</em></li>)}</ul></div>;
      })}
    </details>)}
    {result.warnings.length > 0 && <div className="result-warning"><strong>Engineering review</strong><ul>{result.warnings.map((warning: string, index: number) => <li key={index}>{warning}</li>)}</ul></div>}
  </div>;
}
