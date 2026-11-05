"use client";
/* Python owns section geometry and all engineering calculations. */
/* eslint-disable @typescript-eslint/no-explicit-any */
type Dict = Record<string, any>;

export const CASE_II_DEFAULTS = Object.fromEntries(["left", "right"].map(side => [side, {
  speed: "", radius: "", lane_count: 4, lane_width: "12", initial_slope: side === "left" ? "-0.02" : "0.02",
  pivot_offset: "", runoff_tangent_percent: "", circular_placement_basis: "runoff", runout_placement: "on_tangent",
  acknowledge_spiral_override: false, e_manual: "", Lr_manual: "", Lt_manual: "",
}]));

export function CaseIIInputs({ value, settings, result, onChange, onSettingsChange, speeds, spiral, lengthsOnly }: {
  value: Dict; settings: Dict; result?: Dict; onChange: (changes: Dict) => void; onSettingsChange: (changes: Dict) => void;
  speeds: string[]; spiral: boolean; lengthsOnly: boolean;
}) {
  const derived = settings.case_ii_geometry_mode === "shared_corridor";
  const coordinated = settings.case_ii_placement_mode === "coordinated";
  const changePlacement = (mode: string) => {
    const left = value?.left || {};
    const right = value?.right || {};
    const matching = String(left.runoff_tangent_percent ?? "").trim() !== ""
      && Number(left.runoff_tangent_percent) === Number(right.runoff_tangent_percent)
      && left.circular_placement_basis === right.circular_placement_basis;
    onSettingsChange({ case_ii_placement_mode: mode,
      ...(mode === "coordinated" && !String(settings.runoff_tangent_percent ?? "").trim() && matching
        ? { runoff_tangent_percent: left.runoff_tangent_percent, circular_placement_basis: left.circular_placement_basis } : {}) });
  };
  return <div className="case-ii-inputs full">
    <p className="helper">Both carriageways use the common baseline stations. Left/right look ahead along increasing station. Each median-side travel-lane edge is a fixed pivot at the same relative elevation.</p>
    <div className="form-grid">
      <label className="field full"><span>Carriageway geometry</span><select aria-label="Case II geometry" value={settings.case_ii_geometry_mode || "explicit_radii"} onChange={event => onSettingsChange({case_ii_geometry_mode:event.target.value, ...(event.target.value === "shared_corridor" ? {case_ii_placement_mode:"coordinated"} : {})})}><option value="shared_corridor">Shared corridor — derive radii</option><option value="explicit_radii">Engineer-entered design radii</option></select></label>
      {derived && <label className="field full"><span>Baseline radius (ft) <b>*</b></span><input aria-label="Case II baseline radius" readOnly={settings.geometry_provenance?.source === "LandXML"} type="number" min="0" step="any" value={settings.radius ?? ""} onChange={event => onSettingsChange({radius:event.target.value})} /><small>The baseline may be at a pavement edge, roadway centerline, or median. Imported baseline geometry remains unchanged.</small></label>}
      {!lengthsOnly && <label className="field full"><span>Transition coordination</span><select aria-label="Case II placement" value={settings.case_ii_placement_mode || "independent"} onChange={event => changePlacement(event.target.value)}><option value="coordinated">Coordinated full-super stations</option><option value="independent">Independent placement</option></select></label>}
      {coordinated && !spiral && !lengthsOnly && <>
        <label className="field"><span>Common circular placement basis</span><select aria-label="Case II common placement basis" value={settings.circular_placement_basis || "runoff"} onChange={event => onSettingsChange({circular_placement_basis:event.target.value})}><option value="runoff">Runoff only</option><option value="runoff_runout">Runoff + runout</option></select></label>
        <label className="field"><span>Common transition on tangent (%) <b>*</b></span><input aria-label="Case II common tangent percent" type="number" min="0" max="100" value={settings.runoff_tangent_percent ?? ""} onChange={event => onSettingsChange({runoff_tangent_percent:event.target.value})} /></label><p className="helper full">Applies once to the controlling demand. Both carriageways retain their own rates and rotation lengths.</p>
      </>}
    </div>
    <p className="helper">Pivot offsets are measured from your baseline: positive right, negative left; zero and two offsets on the same side are allowed. {derived ? "Design radii are calculated at each pavement edge nearest the curve center. Offsets are required, including for length checks." : `Offsets position the section without changing your design radii.${lengthsOnly ? " Optional for a length check." : ""}`}</p>
    <div className="case-ii-panels">{["left", "right"].map(side => {
      const inputs = value?.[side] || CASE_II_DEFAULTS[side];
      const update = (key: string, next: any) => onChange({ [side]: { [key]: next } });
      const field = (key: string, label: string, required = true) => <label className="field"><span>{label}{required && <b> *</b>}</span><input aria-label={`${side} carriageway ${label}`} type="number" step="any" value={inputs[key] ?? ""} onChange={event => update(key, event.target.value)} /></label>;
      const negative = String(inputs.initial_slope).startsWith("-");
      return <fieldset key={side} className="case-ii-side"><legend>{side === "left" ? "Left" : "Right"} carriageway</legend><div className="form-grid">
        <label className="field"><span>Design speed <b>*</b></span><select aria-label={`${side} carriageway design speed`} value={inputs.speed} onChange={event => update("speed", event.target.value)}><option value="">Select mph</option>{speeds.map(speed => <option key={speed}>{speed}</option>)}</select></label>
        {derived ? <label className="field"><span>Derived design radius (ft)</span><input aria-label={`${side} carriageway derived radius`} readOnly value={result?.carriageways?.[side]?.radius_provenance?.source === "baseline_offset" ? result.carriageways[side].radius_provenance.design_radius_ft : ""} /></label> : field("radius", "Design radius (ft)")}
        <label className="field"><span>Same-direction lanes</span><select aria-label={`${side} carriageway lanes`} value={inputs.lane_count} onChange={event => update("lane_count", Number(event.target.value))}>{[1,2,3,4,5,6,7].map(count => <option key={count}>{count}</option>)}</select></label>
        {field("lane_width", "Lane width (ft)")}
        {field("pivot_offset", "Pivot baseline offset (ft)", derived || !lengthsOnly)}
        <label className="field"><span>Initial slope (%) <b>*</b></span><input aria-label={`${side} carriageway initial slope`} type="number" min="1.5" max="2" step="0.1" value={["", "-"].includes(String(inputs.initial_slope)) ? "" : Math.abs(Number(inputs.initial_slope)) * 100} onChange={event => update("initial_slope", `${negative ? "-" : ""}${event.target.value === "" ? "" : Math.abs(Number(event.target.value)) / 100}`)} /></label>
        <label className="field"><span>Initial drainage</span><select aria-label={`${side} carriageway initial drainage`} value={negative ? "left" : "right"} onChange={event => update("initial_slope", `${event.target.value === "left" ? "-" : ""}${["", "-"].includes(String(inputs.initial_slope)) ? "" : Math.abs(Number(inputs.initial_slope))}`)}><option value="left">Drains left</option><option value="right">Drains right</option></select></label>
        {!lengthsOnly && (spiral ? <>
          <label className="field full"><span>Runout placement</span><select aria-label={`${side} carriageway runout placement`} value={inputs.runout_placement} onChange={event => update("runout_placement", event.target.value)}><option value="on_tangent">On tangent</option><option value="in_spiral">In spiral</option></select></label>
          <label className="check full"><input type="checkbox" checked={!!inputs.acknowledge_spiral_override} onChange={event => update("acknowledge_spiral_override", event.target.checked)} />Acknowledge project-specific spiral placement and zero-slope drainage review.</label>
        </> : !coordinated && <>
          <label className="field"><span>Circular placement basis</span><select aria-label={`${side} carriageway placement basis`} value={inputs.circular_placement_basis} onChange={event => update("circular_placement_basis", event.target.value)}><option value="runoff">Runoff only</option><option value="runoff_runout">Runoff + runout</option></select></label>
          {field("runoff_tangent_percent", `${inputs.circular_placement_basis === "runoff_runout" ? "Total transition" : "Runoff"} on tangent (%)`)}
        </>)}
      </div><details><summary>Carriageway overrides</summary><div className="form-grid">{field("e_manual", "Manual e (decimal)", false)}{field("Lr_manual", "Runoff Lr (ft)", false)}{field("Lt_manual", "Runout Lt (ft)", false)}</div></details></fieldset>;
    })}</div>
    <p className="helper">Uniform slope per carriageway, travel lanes only. {derived ? "Constant pavement offsets derive the design radii; no new carriageway alignment is constructed." : "Design radii are engineer-entered; the pavement reference is not inferred."} Shoulders and separate carriageway alignments are outside this model.</p>
  </div>;
}

export function CaseIIResults({ result, stations }: { result: Dict; stations?: Dict }) {
  return <div className="case-ii-results"><p className="helper">{result.scope_note}</p>{Object.entries(result.carriageways).map(([side, child]) => {
    const value = child as Dict;
    return <section key={side} aria-label={`${side} carriageway results`}><h3>{side === "left" ? "Left" : "Right"} carriageway</h3>
      <div className="metric-grid"><article><span>Curve cross slope</span><strong>{value.section_transition?.target_slope_label}</strong></article><article><span>Runoff Lr</span><strong>{Number(value.Lr).toFixed(2)}′</strong></article><article><span>Runout Lt</span><strong>{Number(value.Lt).toFixed(2)}′</strong></article></div>
      <p className="helper">{value.section_transition?.note} Lane adjustment: {Number(value.lane_adjustment_factor).toFixed(4)}. {value.baseline_pivot_offset_ft == null ? "Pivot not positioned (length check)." : `Pivot baseline offset: ${value.baseline_pivot_offset_ft} ft (positive right, negative left).`}</p>
      <p className="helper">{value.radius_provenance?.source === "baseline_offset" ? `Baseline radius ${value.radius_provenance.baseline_radius_ft} ft; inside-curve pavement edge offset ${value.radius_provenance.controlling_edge_offset_ft} ft; derived design radius ${value.radius_provenance.design_radius_ft} ft.` : `Engineer-entered design radius ${value.radius_provenance?.design_radius_ft ?? value.inputs?.radius_ft} ft; pavement reference not inferred.`} {result.case_ii_placement_mode === "coordinated" ? "Coordinated full-super stations; separate carriageway rates." : "Independent transition placement."}</p>
      {result.result_type === "spiral_length_check" ? <p>Minimum spiral: {Number(value.minimum_spiral_on_tangent_ft).toFixed(2)} ft with runout on tangent; {Number(value.minimum_spiral_in_spiral_ft).toFixed(2)} ft with runout in spiral.</p> : value.no_transition_required ? <p>Initial section retained throughout the referenced curve; no transition stations are required.</p> : <dl className="case-ii-stations">{[["pnc_ft", "Entry start"], ["full_super_ft", "Full super begins"], ["full_super_out_ft", "Full super ends"], ["pnc_out_ft", "Exit end"]].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{stations?.[side]?.[key] || `${Number(value[key]).toFixed(3)} internal ft`}</dd></div>)}</dl>}
      <details className="criteria-reference"><summary>Calculation sources</summary><ul>{value.calculation_metadata.calculation_sources.map((source: Dict, index: number) => <li key={index}><span>{source.component}</span><b>{source.reference}</b><em>{String(source.mode).replaceAll("_", " ")}</em></li>)}</ul></details>
    </section>;
  })}</div>;
}
