"use client";
/* Python owns section geometry and all engineering calculations. */
/* eslint-disable @typescript-eslint/no-explicit-any */
type Dict = Record<string, any>;

export const CASE_II_DEFAULTS = Object.fromEntries(["left", "right"].map(side => [side, {
  speed: "", radius: "", lane_count: 4, lane_width: "12", initial_slope: side === "left" ? "-0.02" : "0.02",
  pivot_offset: "", runoff_tangent_percent: "", circular_placement_basis: "runoff", runout_placement: "on_tangent",
  acknowledge_spiral_override: false, e_manual: "", Lr_manual: "", Lt_manual: "",
}]));

export function CaseIIInputs({ value, onChange, speeds, spiral, lengthsOnly }: {
  value: Dict; onChange: (changes: Dict) => void; speeds: string[]; spiral: boolean; lengthsOnly: boolean;
}) {
  return <div className="case-ii-inputs full">
    <p className="helper">Both carriageways use the common baseline stations. Left/right look ahead along increasing station. Each inside travel-lane edge is a fixed pivot at the same relative elevation.</p>
    <p className="helper">Pivot offsets locate the inside travel-lane edges: negative left of the common baseline, positive right. They position the drawing without changing design radii or transition lengths.{lengthsOnly && " Optional for a length check."}</p>
    <div className="case-ii-panels">{["left", "right"].map(side => {
      const inputs = value?.[side] || CASE_II_DEFAULTS[side];
      const update = (key: string, next: any) => onChange({ [side]: { [key]: next } });
      const field = (key: string, label: string, required = true) => <label className="field"><span>{label}{required && <b> *</b>}</span><input aria-label={`${side} carriageway ${label}`} type="number" step="any" value={inputs[key] ?? ""} onChange={event => update(key, event.target.value)} /></label>;
      const negative = String(inputs.initial_slope).startsWith("-");
      return <fieldset key={side} className="case-ii-side"><legend>{side === "left" ? "Left" : "Right"} carriageway</legend><div className="form-grid">
        <label className="field"><span>Design speed <b>*</b></span><select aria-label={`${side} carriageway design speed`} value={inputs.speed} onChange={event => update("speed", event.target.value)}><option value="">Select mph</option>{speeds.map(speed => <option key={speed}>{speed}</option>)}</select></label>
        {field("radius", "Design radius (ft)")}
        <label className="field"><span>Same-direction lanes</span><select aria-label={`${side} carriageway lanes`} value={inputs.lane_count} onChange={event => update("lane_count", Number(event.target.value))}>{[1,2,3,4,5,6,7].map(count => <option key={count}>{count}</option>)}</select></label>
        {field("lane_width", "Lane width (ft)")}
        {field("pivot_offset", "Pivot baseline offset (ft)", !lengthsOnly)}
        <label className="field"><span>Initial slope (%) <b>*</b></span><input aria-label={`${side} carriageway initial slope`} type="number" min="1.5" max="2" step="0.1" value={["", "-"].includes(String(inputs.initial_slope)) ? "" : Math.abs(Number(inputs.initial_slope)) * 100} onChange={event => update("initial_slope", `${negative ? "-" : ""}${event.target.value === "" ? "" : Math.abs(Number(event.target.value)) / 100}`)} /></label>
        <label className="field"><span>Initial drainage</span><select aria-label={`${side} carriageway initial drainage`} value={negative ? "left" : "right"} onChange={event => update("initial_slope", `${event.target.value === "left" ? "-" : ""}${["", "-"].includes(String(inputs.initial_slope)) ? "" : Math.abs(Number(inputs.initial_slope))}`)}><option value="left">Drains left</option><option value="right">Drains right</option></select></label>
        {!lengthsOnly && (spiral ? <>
          <label className="field full"><span>Runout placement</span><select aria-label={`${side} carriageway runout placement`} value={inputs.runout_placement} onChange={event => update("runout_placement", event.target.value)}><option value="on_tangent">On tangent</option><option value="in_spiral">In spiral</option></select></label>
          <label className="check full"><input type="checkbox" checked={!!inputs.acknowledge_spiral_override} onChange={event => update("acknowledge_spiral_override", event.target.checked)} />Acknowledge project-specific spiral placement and zero-slope drainage review.</label>
        </> : <>
          <label className="field"><span>Circular placement basis</span><select aria-label={`${side} carriageway placement basis`} value={inputs.circular_placement_basis} onChange={event => update("circular_placement_basis", event.target.value)}><option value="runoff">Runoff only</option><option value="runoff_runout">Runoff + runout</option></select></label>
          {field("runoff_tangent_percent", `${inputs.circular_placement_basis === "runoff_runout" ? "Total transition" : "Runoff"} on tangent (%)`)}
        </>)}
      </div><details><summary>Carriageway overrides</summary><div className="form-grid">{field("e_manual", "Manual e (decimal)", false)}{field("Lr_manual", "Runoff Lr (ft)", false)}{field("Lt_manual", "Runout Lt (ft)", false)}</div></details></fieldset>;
    })}</div>
    <p className="helper">Uniform slope per carriageway, travel lanes only. Design radii are explicit inputs; they do not create or modify the baseline alignment.</p>
  </div>;
}

export function CaseIIResults({ result, stations }: { result: Dict; stations?: Dict }) {
  return <div className="case-ii-results"><p className="helper">{result.scope_note}</p>{Object.entries(result.carriageways).map(([side, child]) => {
    const value = child as Dict;
    return <section key={side} aria-label={`${side} carriageway results`}><h3>{side === "left" ? "Left" : "Right"} carriageway</h3>
      <div className="metric-grid"><article><span>Curve cross slope</span><strong>{value.section_transition?.target_slope_label}</strong></article><article><span>Runoff Lr</span><strong>{Number(value.Lr).toFixed(2)}′</strong></article><article><span>Runout Lt</span><strong>{Number(value.Lt).toFixed(2)}′</strong></article></div>
      <p className="helper">{value.section_transition?.note} Lane adjustment: {Number(value.lane_adjustment_factor).toFixed(4)}. {value.baseline_pivot_offset_ft == null ? "Pivot not positioned (length check)." : `Pivot baseline offset: ${value.baseline_pivot_offset_ft} ft (positive right, negative left).`}</p>
      {result.result_type === "spiral_length_check" ? <p>Minimum spiral: {Number(value.minimum_spiral_on_tangent_ft).toFixed(2)} ft with runout on tangent; {Number(value.minimum_spiral_in_spiral_ft).toFixed(2)} ft with runout in spiral.</p> : value.no_transition_required ? <p>Initial section retained throughout the referenced curve; no transition stations are required.</p> : <dl className="case-ii-stations">{[["pnc_ft", "Entry start"], ["full_super_ft", "Full super begins"], ["full_super_out_ft", "Full super ends"], ["pnc_out_ft", "Exit end"]].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{stations?.[side]?.[key] || `${Number(value[key]).toFixed(3)} internal ft`}</dd></div>)}</dl>}
      <details className="criteria-reference"><summary>Calculation sources</summary><ul>{value.calculation_metadata.calculation_sources.map((source: Dict, index: number) => <li key={index}><span>{source.component}</span><b>{source.reference}</b><em>{String(source.mode).replaceAll("_", " ")}</em></li>)}</ul></details>
    </section>;
  })}</div>;
}
