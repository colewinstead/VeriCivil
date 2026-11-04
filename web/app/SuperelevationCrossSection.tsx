"use client";

/* Shared Python presentation packets are JSON dictionaries. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useEffectEvent, useRef, useState } from "react";
import ControlIcon from "./ControlIcon";

type Dict = Record<string, any>;

export default function SuperelevationCrossSection({ diagrams, activeCurveIndex, inspector, pending, error, onStation }: {
  diagrams: Dict[]; activeCurveIndex: number; inspector: Dict | null; pending: boolean; error: string;
  onStation: (station: number | string, curveIndex: number) => void;
}) {
  const [chosenCurve, setChosenCurve] = useState<number | null>(null);
  const index = chosenCurve ?? inspector?.curve_index ?? activeCurveIndex;
  const diagram = diagrams.find(item => item.curve_index === index) || diagrams[0];
  const curveIndex = Number(diagram?.curve_index ?? 0);
  const start = Number(diagram?.domain.start_ft ?? 0);
  const end = Number(diagram?.domain.end_ft ?? 0);
  const [target, setTarget] = useState<{ diagram: Dict; inspector: Dict | null; station: number } | null>(null);
  const station = target && target.diagram === diagram && target.inspector === inspector ? target.station
    : Math.max(start, Math.min(end, inspector?.curve_index === curveIndex ? inspector.station_ft : start));
  const [draft, setDraft] = useState<{ curveIndex: number; text: string } | null>(null);
  const stationText = draft?.curveIndex === curveIndex ? draft.text
    : inspector?.curve_index === curveIndex ? inspector.station : "";
  const [trueScale, setTrueScale] = useState(false);
  const scrubber = useRef<HTMLInputElement>(null);
  const lastRequest = useRef<{ curveIndex: number; station: number | string } | null>(null);
  const inspect = (value: number | string) => {
    lastRequest.current = { curveIndex, station: value };
    onStation(value, curveIndex);
  };
  useEffect(() => {
    if (inspector?.curve_index === curveIndex) lastRequest.current = { curveIndex, station: inspector.station_ft };
  }, [inspector, curveIndex]);
  const initialize = useEffectEvent(() => {
    if (!diagram) return;
    const remembered = lastRequest.current?.curveIndex === curveIndex ? lastRequest.current.station : station;
    inspect(typeof remembered === "number" ? Math.max(start, Math.min(end, remembered)) : remembered);
  });
  useEffect(() => { initialize(); }, [diagram, onStation]);

  const scrollStation = useEffectEvent((event: WheelEvent) => {
    if (document.activeElement !== scrubber.current || !event.deltaY) return;
    event.preventDefault();
    const next = Math.max(start, Math.min(end, station + (event.deltaY > 0 ? 1 : -1)));
    setDraft(null);
    setTarget({ diagram, inspector, station: next });
    inspect(next);
  });
  useEffect(() => {
    const input = scrubber.current;
    if (!input || !diagram) return;
    const wheel = (event: WheelEvent) => scrollStation(event);
    input.addEventListener("wheel", wheel, { passive: false });
    return () => input.removeEventListener("wheel", wheel);
  }, [diagram]);

  if (!diagram) return <div className="analysis-empty">Calculate a curve to inspect its cross section by station.</div>;
  const selected = inspector?.curve_index === curveIndex && inspector.station_ft === station ? inspector : null;
  const section = selected?.cross_section;
  const model = diagram.cross_section;
  const physical = model?.mode === "physical";
  const exaggeration = physical && trueScale ? 1 : 5;
  const bounds = model?.bounds;
  // One uniform SVG scale preserves physical proportions; only vertical exaggeration changes them.
  const span = bounds ? bounds.x_max - bounds.x_min : 1;
  const scale = 760 / Math.max(span, 0.001);
  const x = (value: number) => 70 + (bounds.x_max - value) * scale;
  const y = (value: number) => 210 - value * scale * exaggeration;
  const top = bounds ? Math.min(0, y(bounds.y_max) - 85) : 0;
  const bottom = bounds ? Math.max(360, y(bounds.y_min) + 85) : 360;
  const events = (diagram.snap_points || []).map((event: Dict) => Number(event.station_ft)).filter((value: number) => value >= start && value <= end);
  const previous = events.filter((value: number) => value < station - 1e-7).at(-1);
  const next = events.find((value: number) => value > station + 1e-7);
  const selectStation = (value: number) => { setDraft(null); setTarget({ diagram, inspector, station: value }); inspect(value); };

  return <div className="cross-section-view" role="tabpanel" aria-label="Cross Section">
    <div className="cross-section-controls">
      <label className="field"><span>Curve</span><select aria-label="Cross-section curve" value={curveIndex} onChange={event => setChosenCurve(Number(event.target.value))}>
        {diagrams.map(item => <option key={item.curve_index} value={item.curve_index}>{item.curve_name}</option>)}
      </select></label>
      <form className="cross-section-station" onSubmit={event => { event.preventDefault(); if (stationText.trim()) inspect(stationText); }}>
        <label className="field"><span>Station</span><input aria-label="Cross-section station" value={stationText} placeholder="Enter station" onChange={event => setDraft({ curveIndex, text: event.target.value })} /></label>
        <button type="submit" disabled={!stationText.trim()}>Go</button>
      </form>
      {physical && <label className="cross-section-scale"><input type="checkbox" checked={trueScale} onChange={event => setTrueScale(event.target.checked)} /> True scale</label>}
    </div>
    <div className="cross-section-heading"><div><h4>{model?.title || "Cross section unavailable"}</h4><p>Looking ahead along increasing station</p></div><strong>{physical && trueScale ? "True scale · 1×" : "Vertical exaggeration · 5×"}</strong></div>
    <div className="cross-section-scrubber">
      <button aria-label="Previous section event" disabled={previous === undefined} onClick={() => selectStation(previous)}><ControlIcon name="left" /></button>
      <input ref={scrubber} type="range" min={start} max={end} step="any" value={station} aria-label="Cross-section station scrubber" aria-valuetext={selected?.station || `${station.toFixed(3)} internal ft`}
        onChange={event => selectStation(Number(event.target.value))}
        onKeyDown={event => {
          const offset = event.key === "ArrowLeft" || event.key === "ArrowDown" ? -1 : event.key === "ArrowRight" || event.key === "ArrowUp" ? 1 : 0;
          if (offset) { event.preventDefault(); selectStation(Math.max(start, Math.min(end, station + offset))); }
        }} />
      <button aria-label="Next section event" disabled={next === undefined} onClick={() => selectStation(next)}><ControlIcon name="right" /></button>
    </div>
    <div className="cross-section-readout"><strong>{selected?.station || "Selecting station…"}</strong><span>{station.toFixed(3)} internal ft · Focus the slider to scroll by station</span></div>
    {error && <p className="cross-section-error" role="alert">{error}</p>}
    <div className="cross-section-drawing" aria-busy={pending}>
      {!selected ? <div className="analysis-empty" role="status">{error ? "Correct the station or select the slider to continue." : "Loading cross section…"}</div> : section?.mode === "unavailable" || !bounds ? <div className="analysis-empty">{section?.message || model?.message || "Section geometry is unavailable. Recalculate this curve."}</div> : <svg viewBox={`0 ${top} 900 ${bottom - top}`} role="img" aria-label={`${section.title} at ${selected.station}, ${exaggeration} times vertical scale. Looking ahead along increasing station. Left to right: ${section.segments.map((segment: Dict) => `${segment.name}: ${segment.slope_label}${physical ? `, ${segment.width_ft} ft wide` : ""}`).join("; ")}. ${section.pivots ? `Two level median-side pivots; ${section.median_gap_ft} ft median interval; heights relative to the common profile.` : section.pivot ? `Fixed ${section.pivot.label} pivot; heights are relative to this pivot.` : section.message}`}>
        <line className="section-datum" x1="45" x2="855" y1={y(0)} y2={y(0)} />
        <text className="section-orientation" x="45" y={top + 24}>LEFT</text><text className="section-orientation" x="855" y={top + 24} textAnchor="end">RIGHT</text>
        {section.segments.map((segment: Dict) => {
          const midX = (x(segment.left.x) + x(segment.right.x)) / 2;
          const midY = (y(segment.left.y) + y(segment.right.y)) / 2;
          return <g key={segment.name} className={`section-segment section-${segment.side}`}>
            <title>{segment.name}: {segment.slope_label}{physical ? `, ${segment.width_ft} ft wide. Left edge ${segment.left.y.toFixed(4)} ft; right edge ${segment.right.y.toFixed(4)} ft relative to pivot.` : ". Schematic span; physical width is unspecified."}</title>
            <line x1={x(segment.left.x)} y1={y(segment.left.y)} x2={x(segment.right.x)} y2={y(segment.right.y)} />
            <circle cx={x(segment.left.x)} cy={y(segment.left.y)} r="3" /><circle cx={x(segment.right.x)} cy={y(segment.right.y)} r="3" />
            <text x={midX} y={midY - 34} textAnchor="middle">{segment.display_label || segment.name}</text>
            <text className="section-slope" x={midX} y={midY - 13} textAnchor="middle">{segment.slope_label}</text>
            {physical && <text x={midX} y={midY + 28} textAnchor="middle">{Number(segment.width_ft).toFixed(1)} ft</text>}
          </g>;
        })}
        {section.pivots && <g className="section-median-gap"><line className="section-datum" x1={x(section.pivots[0].x)} x2={x(section.pivots[1].x)} y1={y(0) - 60} y2={y(0) - 60} /><text x={(x(section.pivots[0].x) + x(section.pivots[1].x)) / 2} y={y(0) - 70} textAnchor="middle">Median interval · {Number(section.median_gap_ft).toFixed(1)} ft</text></g>}
        {(section.pivots || (section.pivot ? [section.pivot] : [])).map((pivot: Dict) => <g key={pivot.label} className="section-pivot"><circle cx={x(pivot.x)} cy={y(0)} r="7" /><line x1={x(pivot.x)} x2={x(pivot.x)} y1={y(0) + 10} y2={bottom - 38} /><text x={x(pivot.x)} y={bottom - 18} textAnchor={section.pivots ? pivot.label.startsWith("Left") ? "end" : "start" : "middle"}>Fixed pivot · {section.pivots ? pivot.label.replace(" median-side travel-lane edge", " carriageway") : pivot.label}</text></g>)}
      </svg>}
    </div>
    {section?.segments?.length > 0 && <div className="cross-section-mobile-labels"><p>Slopes, left to right</p><dl>{section.segments.map((segment: Dict) => <div key={segment.name} className={`section-segment section-${segment.side}`}><dt>{segment.name}</dt><dd><strong>{segment.slope_label}</strong>{physical && <span> · {Number(segment.width_ft).toFixed(1)} ft</span>}</dd></div>)}</dl>{section.pivot && <p>Fixed pivot · {section.pivot.label}</p>}</div>}
    <p className="cross-section-note">{model?.message}</p>
    {physical && section?.segments?.length > 0 && <div className="cross-section-table"><table><caption>Lane edges relative to the fixed pivot (ft)</caption><thead><tr><th>Lane</th><th>Slope</th><th>Left edge</th><th>Right edge</th></tr></thead><tbody>{section.segments.map((segment: Dict) => <tr key={segment.name}><td>{segment.name}</td><td>{segment.slope_label}</td><td>{segment.left.y.toFixed(4)}</td><td>{segment.right.y.toFixed(4)}</td></tr>)}</tbody></table></div>}
    <p className="cross-section-note">Slope signs follow each recorded lane side, outward from alignment. <span role="status">{pending ? "Updating station…" : ""}</span></p>
  </div>;
}
