"use client";

/* Pyodide service responses are JSON dictionaries. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { MouseEvent, PointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import SuperelevationPlanView from "./SuperelevationPlanView";

type Dict = Record<string, any>;
type AnalysisView = "diagram" | "plan" | "qa";

function interpolate(points: Dict[], station: number) {
  if (!points.length) return 0;
  if (station <= points[0].station_ft) return points[0].slope_pct;
  if (station >= points[points.length - 1].station_ft) return points[points.length - 1].slope_pct;
  const index = points.findIndex((point) => point.station_ft >= station);
  const prior = points[index - 1];
  const next = points[index];
  if (next.station_ft === prior.station_ft) return next.slope_pct;
  const fraction = (station - prior.station_ft) / (next.station_ft - prior.station_ft);
  return prior.slope_pct + fraction * (next.slope_pct - prior.slope_pct);
}

function profileValue(points: Dict[], station: number) {
  if (!points.length) return null;
  const start = Number(points[0].station_ft);
  const end = Number(points[points.length - 1].station_ft);
  return station >= start && station <= end ? interpolate(points, station) : null;
}

function chartProfiles(diagram: Dict): Dict[] {
  if (diagram.section_profiles?.length) return diagram.section_profiles;
  return ["left","right"].filter(side=>diagram.profiles[side]?.length).map(side=>({key:side==="left"?"Left":"Right",name:side==="left"?"L":"R",side,points:diagram.profiles[side]}));
}

function chartRows(corridor: Dict | null, visibleDomain: [number, number]) {
  const diagrams = corridor?.curves || [];
  if (!diagrams.length) return [];
  const [start, end] = visibleDomain;
  const samples = Array.from({ length: 721 }, (_, index) => start + ((end - start) * index / 720));
  const stations = new Set<number>(samples);
  diagrams.forEach((diagram: Dict) => (chartProfiles(diagram).flatMap(profile=>profile.points) as Dict[])
    .forEach((point) => {
      const station = Number(point.station_ft);
      if (station >= start && station <= end) stations.add(station);
    }));
  return [...stations].sort((a, b) => a - b).map((station) => {
    const row: Dict = { station };
    diagrams.forEach((diagram: Dict) => {
      const key = `curve${diagram.curve_index}`;
      chartProfiles(diagram).forEach(profile=>{row[`${key}${profile.key}`]=profileValue(profile.points,station);});
    });
    return row;
  });
}

const CURVE_COLORS = ["#49c6b3", "#efbd5c", "#78a9ff", "#ee806f", "#a7cf72", "#d49be8", "#76c7df", "#f19a55"];

function stationTick(value: number) {
  const hundreds = Math.floor(value / 100);
  return `${hundreds}+${(value - hundreds * 100).toFixed(0).padStart(2, "0")}`;
}

export default function SuperelevationAnalysis({
  corridor,
  plan,
  activeCurveIndex,
  qa,
  inspector,
  highlights,
  onChartStation,
  onFinding,
}: {
  corridor: Dict | null;
  plan: Dict | null;
  activeCurveIndex: number;
  qa: Dict | null;
  inspector: Dict | null;
  highlights: Dict[];
  onChartStation: (station: number, curveIndex: number) => void;
  onFinding: (finding: Dict) => void;
}) {
  const [view, setView] = useState<AnalysisView>("diagram");
  const [filter, setFilter] = useState("all");
  const [snapEvents, setSnapEvents] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [zoomState, setZoomState] = useState<{ key: string; domain: [number, number] } | null>(null);
  const chartFrameRef = useRef<HTMLDivElement>(null);
  const panRef = useRef<{ x: number; domain: [number, number] } | null>(null);
  const didDragRef = useRef(false);
  const diagrams: Dict[] = corridor?.curves || [];
  const findings = (qa?.findings || []).filter((finding: Dict) => filter === "all" || finding.severity === filter);
  const selectedCurveIndex = diagrams.some((item) => item.curve_index === activeCurveIndex)
    ? activeCurveIndex : Number(diagrams[0]?.curve_index ?? 0);
  const visibleMarkers = diagrams.flatMap((diagram) => (diagram.markers || [])
    .filter((marker: Dict) => ["PC", "PT", "TS", "SC", "CS", "ST", "STATION EQUATION"].includes(marker.kind))
    .map((marker: Dict) => ({ ...marker, curve_index: diagram.curve_index, curve_name: diagram.curve_name })));
  const fullDomain = useMemo<[number, number]>(() => [
    Number(corridor?.domain?.start_ft || 0),
    Number(corridor?.domain?.end_ft || 0),
  ], [corridor]);
  const zoomKey = `${corridor?.curve_count || 0}:${fullDomain[0]}:${fullDomain[1]}`;
  const activeDomain = zoomState?.key === zoomKey ? zoomState.domain : fullDomain;
  const data = useMemo(() => chartRows(corridor, activeDomain), [activeDomain, corridor]);

  const zoom = useCallback((factor: number, anchorRatio = 0.5) => {
    if (!corridor || fullDomain[1] <= fullDomain[0]) return;
    const [currentStart, currentEnd] = activeDomain;
    const fullSpan = fullDomain[1] - fullDomain[0];
    const nextSpan = Math.min(fullSpan, Math.max(Math.max(fullSpan / 120, 1), (currentEnd - currentStart) * factor));
    const anchorStation = currentStart + (currentEnd - currentStart) * anchorRatio;
    let start = anchorStation - nextSpan * anchorRatio;
    let end = start + nextSpan;
    if (start < fullDomain[0]) { start = fullDomain[0]; end = start + nextSpan; }
    if (end > fullDomain[1]) { end = fullDomain[1]; start = end - nextSpan; }
    setZoomState(nextSpan >= fullSpan - 1e-6 ? null : { key: zoomKey, domain: [start, end] });
  }, [activeDomain, corridor, fullDomain, zoomKey]);

  const panBy = (fraction: number) => {
    const span = activeDomain[1] - activeDomain[0];
    if (span >= fullDomain[1] - fullDomain[0] - 1e-6) return;
    const shift = span * fraction;
    let start = activeDomain[0] + shift;
    let end = activeDomain[1] + shift;
    if (start < fullDomain[0]) { start = fullDomain[0]; end = start + span; }
    if (end > fullDomain[1]) { end = fullDomain[1]; start = end - span; }
    setZoomState({ key: zoomKey, domain: [start, end] });
  };

  useEffect(() => {
    const frame = chartFrameRef.current;
    if (!frame || !corridor) return;
    const wheelZoom = (event: globalThis.WheelEvent) => {
      event.preventDefault();
      const bounds = frame.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / Math.max(bounds.width, 1)));
      zoom(event.deltaY < 0 ? 0.78 : 1.28, ratio);
    };
    frame.addEventListener("wheel", wheelZoom, { passive: false });
    return () => frame.removeEventListener("wheel", wheelZoom);
  }, [corridor, zoom]);

  useEffect(() => {
    if (!expanded) return;
    const priorOverflow = document.body.style.overflow;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setExpanded(false); };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", close);
    return () => {
      document.body.style.overflow = priorOverflow;
      window.removeEventListener("keydown", close);
    };
  }, [expanded]);

  const curveAtStation = (station: number) => {
    const covering = diagrams.filter((item) => station >= Number(item.domain.start_ft) && station <= Number(item.domain.end_ft));
    return covering.find((item) => item.curve_index === selectedCurveIndex) || covering[0] || diagrams[0];
  };

  const snappedStation = (station: number, diagram: Dict) => {
    if (!snapEvents || !diagram?.snap_points?.length) return station;
    const nearest = diagram.snap_points.reduce((best: Dict, point: Dict) =>
      Math.abs(Number(point.station_ft) - station) < Math.abs(Number(best.station_ft) - station) ? point : best
    );
    const chartWidth = chartFrameRef.current?.querySelector(".chart-canvas")?.getBoundingClientRect().width || 320;
    const threshold = Math.max(Math.min((activeDomain[1] - activeDomain[0]) * 12 / Math.max(chartWidth, 1), 5), 0.25);
    return Math.abs(Number(nearest.station_ft) - station) <= threshold ? Number(nearest.station_ft) : station;
  };

  const selectPoint = (event: MouseEvent<HTMLDivElement>) => {
    if (didDragRef.current) { didDragRef.current = false; return; }
    const bounds = event.currentTarget.getBoundingClientRect();
    const plotLeft = bounds.left + 42;
    const plotWidth = Math.max(bounds.width - 42 - 18, 1);
    const ratio = Math.max(0, Math.min(1, (event.clientX - plotLeft) / plotWidth));
    const station = activeDomain[0] + ratio * (activeDomain[1] - activeDomain[0]);
    const curve = curveAtStation(station);
    if (curve) onChartStation(snappedStation(station, curve), Number(curve.curve_index));
  };

  const startPan = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || activeDomain[1] - activeDomain[0] >= fullDomain[1] - fullDomain[0] - 1e-6) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    panRef.current = { x: event.clientX, domain: [...activeDomain] };
    didDragRef.current = false;
    setDragging(true);
  };

  const movePan = (event: PointerEvent<HTMLDivElement>) => {
    const pan = panRef.current;
    if (!pan) return;
    const width = Math.max(event.currentTarget.getBoundingClientRect().width, 1);
    const span = pan.domain[1] - pan.domain[0];
    const shift = -(event.clientX - pan.x) / width * span;
    if (Math.abs(event.clientX - pan.x) > 3) didDragRef.current = true;
    let start = pan.domain[0] + shift;
    let end = pan.domain[1] + shift;
    if (start < fullDomain[0]) { start = fullDomain[0]; end = start + span; }
    if (end > fullDomain[1]) { end = fullDomain[1]; start = end - span; }
    setZoomState({ key: zoomKey, domain: [start, end] });
  };

  const endPan = (event: PointerEvent<HTMLDivElement>) => {
    if (panRef.current) event.currentTarget.releasePointerCapture(event.pointerId);
    panRef.current = null;
    setDragging(false);
  };

  return <section className={`analysis-workspace${expanded ? " analysis-expanded" : ""}`}>
    <div className="analysis-tabs" role="tablist" aria-label="Engineering analysis">
      <button role="tab" aria-selected={view === "diagram"} className={view === "diagram" ? "active" : ""} onClick={() => setView("diagram")}>Diagram</button>
      <button role="tab" aria-selected={view === "plan"} className={view === "plan" ? "active" : ""} onClick={() => setView("plan")}>Plan View</button>
      <button role="tab" aria-selected={view === "qa"} className={view === "qa" ? "active" : ""} onClick={() => setView("qa")}>Corridor QA{qa && <span className={`status-dot ${qa.status}`} />}</button>
      <button className="expand-analysis" title={expanded ? "Close large analysis view" : "Open large analysis view"} onClick={() => setExpanded(!expanded)}>{expanded ? "Close" : "Expand"}</button>
    </div>

    {view === "diagram" && <div className="diagram-layout">
      {!diagrams.length ? <div className="analysis-empty">Calculate curves to view the corridor lane profiles.</div> : <>
        <div ref={chartFrameRef} className="chart-frame" aria-label="Left and right lane slope by station">
          <div className="chart-tools"><span>{diagrams.length} curve{diagrams.length === 1 ? "" : "s"} · {stationTick(activeDomain[0])} to {stationTick(activeDomain[1])}</span><label title="Snap selections to nearby lane events"><input type="checkbox" checked={snapEvents} onChange={(event) => setSnapEvents(event.target.checked)} /> Snap events</label><button title="Pan toward corridor start" aria-label="Pan left" onClick={() => panBy(-0.72)}>←</button><button title="Pan toward corridor end" aria-label="Pan right" onClick={() => panBy(0.72)}>→</button><button title="Zoom out" aria-label="Zoom out" onClick={() => zoom(1.28)}>−</button><button title="Zoom in" aria-label="Zoom in" onClick={() => zoom(0.78)}>+</button><button title="Reset zoom" aria-label="Reset zoom" onClick={() => setZoomState(null)}>Reset</button></div>
          <div className={`chart-canvas${dragging ? " dragging" : ""}`} onClick={selectPoint} onPointerDown={startPan} onPointerMove={movePan} onPointerUp={endPan} onPointerCancel={endPan}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 26, right: 18, bottom: 12, left: 0 }}>
                <CartesianGrid stroke="#2b3b37" strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="station" type="number" domain={activeDomain} allowDataOverflow tickFormatter={stationTick} stroke="#81918c" tick={{ fontSize: 10 }} />
                <YAxis unit="%" stroke="#81918c" tick={{ fontSize: 10 }} width={42} />
                <Tooltip formatter={(value) => [value == null ? "" : `${Number(value).toFixed(2)}%`]} labelFormatter={(value) => stationTick(Number(value))} contentStyle={{ background: "#101c19", border: "1px solid #334a44", borderRadius: 6, fontSize: 11 }} />
                <Legend iconType="line" wrapperStyle={{ fontSize: 10 }} />
                <ReferenceLine y={0} stroke="#8a9995" strokeWidth={1.2} />
                {highlights.map((item, index) => <ReferenceArea key={`${item.code}-${index}`} x1={item.start_ft} x2={item.end_ft} fill={item.severity === "block" ? "#ef6a5b" : "#efbd5c"} fillOpacity={0.16} />)}
                {visibleMarkers.map((marker: Dict, index: number) => <ReferenceLine key={`${marker.curve_index}-${marker.label}-${marker.station_ft}-${index}`} x={marker.station_ft} stroke={marker.kind === "STATION EQUATION" ? "#efbd5c" : "#57736b"} strokeDasharray="3 4" label={marker.curve_index === selectedCurveIndex ? { value: marker.kind === "STATION EQUATION" ? marker.label : `${marker.curve_name} ${marker.kind}`, position: "insideTop", fill: "#aebbb7", fontSize: 9 } : undefined} />)}
                {inspector && <ReferenceLine x={inspector.station_ft} stroke="#ffffff" strokeWidth={1.4} />}
                {diagrams.flatMap((diagram, index) => {
                  const color = CURVE_COLORS[index % CURVE_COLORS.length];
                  const active = Number(diagram.curve_index) === selectedCurveIndex;
                  const key = `curve${diagram.curve_index}`;
                  return chartProfiles(diagram).map(profile=><Line key={`${key}-${profile.key}`} type="linear" dataKey={`${key}${profile.key}`} name={`${diagram.curve_name} · ${profile.name}`} stroke={color} strokeWidth={active ? 2.8 : 1.7} strokeOpacity={active ? 1 : 0.72} strokeDasharray={profile.side==="right"?"7 4":undefined} dot={false} activeDot={{r:4}} isAnimationActive={false} connectNulls={false}/>);
                })}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="diagram-inspector">
          <div className="inspector-heading"><span>{inspector?.curve_name || "Selected station"}</span><strong>{inspector?.station || "Select the plot"}</strong>{inspector && <small>{Number(inspector.station_ft).toFixed(3)} internal ft</small>}</div>
          {inspector ? <div className="inspector-lanes">{Object.keys(inspector.lanes).map((lane) => <article key={lane}>
            <div><span>{lane}</span><strong>{inspector.lanes[lane].slope_label}</strong></div>
            <p>{inspector.lanes[lane].phase}</p>
            <b>{inspector.lanes[lane].criterion.reference}</b>
            <small>{inspector.lanes[lane].criterion.component} · {inspector.lanes[lane].criterion.mode.replace("_", " ")}</small>
          </article>)}</div> : <p className="inspector-empty">Click the profile to inspect slope and criteria at that station.</p>}
        </div>
      </>}
    </div>}

    {view === "plan" && (plan ? <SuperelevationPlanView plan={plan} /> : <div className="analysis-empty">Load LandXML to view the alignment plan.</div>)}

    {view === "qa" && <div className="qa-dashboard">
      {!qa ? <div className="analysis-empty">Load LandXML to analyze the corridor.</div> : <>
        <div className="qa-summary">
          <article className={`qa-overall ${qa.status}`}><span>Corridor</span><strong>{qa.status}</strong><small>{qa.curve_count} reviewed{qa.excluded_count ? ` · ${qa.excluded_count} excluded` : ""}</small></article>
          {(["pass", "review", "block"] as const).map((status) => <button key={status} className={filter === status ? "selected" : ""} onClick={() => setFilter(filter === status ? "all" : status)}><span>{status}</span><strong>{qa.counts?.[status] || 0}</strong></button>)}
        </div>
        <div className="qa-filters"><button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>All findings</button>{(["review", "block"] as const).map((status) => <button key={status} className={filter === status ? "active" : ""} onClick={() => setFilter(status)}>{status}</button>)}</div>
        <div className="qa-findings">
          {findings.length ? findings.map((finding: Dict, index: number) => <button key={`${finding.code}-${index}`} onClick={() => { setView("diagram"); onFinding(finding); }}>
            <span className={`severity ${finding.severity}`}>{finding.severity}</span>
            <div><strong>{finding.message}</strong><small>{finding.code.replaceAll("_", " ")}{finding.start ? ` · ${finding.start}${finding.end && finding.end !== finding.start ? ` to ${finding.end}` : ""}` : ""}</small>{finding.details && <p>{finding.details}</p>}</div>
            <b aria-hidden="true">›</b>
          </button>) : <div className="qa-pass"><strong>No {filter === "all" ? "corridor" : filter} findings</strong><span>The calculated set satisfies the current QA checks.</span></div>}
        </div>
      </>}
    </div>}
  </section>;
}
