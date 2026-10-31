"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DesktopHost, DesktopProject } from "@/lib/desktop";
import { commit, history, redo, undo, type History } from "@/lib/typicals-history";
import "./typicals.css";

type Point = [number, number];
type Side = { lane_width_ft: number; lane_slope_pct: number; shoulder_width_ft: number; shoulder_slope_pct: number; shoulder_paved: boolean; roadside_hv: number; roadside_height_ft: number };
type Level = { name: string; description: string; rgb: string | null; lineweight_mm: number | null; bylevel_color: string | null; bylevel_weight: string | null; bylevel_style: string | null; dash_ft: number[] | null };
type Catalog = { format: string; version: number; source: string; revision: string; extraction_status: string; levels: Level[] };
type Project = {
  format: string; version: number; units: string; origin: Point; left: Side; right: Side;
  metadata: { title: string; route: string; construction: string; stations: string; notes: string[] };
  layers: { id: string; name: string; material: string; thickness_in: number }[]; ground: Point[];
  constraints: { locked_points: Record<string, Point> }; drafting: { scale_ft_per_in: number; text_height_in: number; dimension_gap_in: number; font: string; precision: number };
  print: { monochrome: boolean; width_in: number; height_in: number; lineweights_mm?: Record<string, number> }; annotations: Record<string, Point>;
  level_mappings: Record<string, string>; catalog: Catalog | null;
};
type Primitive = { kind: "line" | "text" | "circle" | "polygon"; points?: Point[]; text_width?: number; rotation?: number; a: Point; b?: Point; text?: string; height?: number; radius?: number; role: string; component: string };
type Scene = { bounds: [number, number, number, number]; primitives: Primitive[]; warnings: string[];
  styles: Record<string, { name: string; rgb: string; lineweight_mm: number; dash_ft: number[]; resolved: boolean; plot: boolean }>;
  geometry: { points: Record<string, Point>; layers: { depth_ft: number }[] } };
type Export = { content_base64: string; report: Record<string, unknown> | null };
const roles = ["surface", "pavement", "left_slope", "right_slope", "ground", "centerline", "dimensions", "dimension_text", "slopes", "callouts", "text"];

function Numeric({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  return <label>{label}<input key={value} type="number" step="any" defaultValue={value} onBlur={e => { const draft = e.currentTarget.value; e.currentTarget.value = String(value); if (draft !== String(value)) onChange(draft.trim() ? Number(draft) : NaN); }} onKeyDown={e => { if (e.key === "Escape") e.currentTarget.value = String(value); if (e.key === "Enter" || e.key === "Escape") e.currentTarget.blur(); }} /></label>;
}

export default function TypicalsApp({ desktop }: { desktop?: DesktopHost }) {
  const [state, setState] = useState<History<Project> | null>(null);
  const [scene, setScene] = useState<Scene | null>(null);
  const [mode, setMode] = useState<"cad" | "print">("cad");
  const [sheet, setSheet] = useState("");
  const [status, setStatus] = useState("Loading shared Python engine…");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  const [selected, setSelected] = useState("left_lane");
  const [tab, setTab] = useState("Section");
  const [hidden, setHidden] = useState<string[]>([]);
  const [view, setView] = useState<[number, number, number, number] | null>(null);
  const [cursor, setCursor] = useState<Point>([0, 0]);
  const [measure, setMeasure] = useState(false);
  const [snapping, setSnapping] = useState(true);
  const [measurePoints, setMeasurePoints] = useState<Point[]>([]);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const worker = useRef<Worker | null>(null);
  const sequence = useRef(0);
  const requests = useRef(new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>());
  const svgRef = useRef<SVGSVGElement | null>(null);
  const drag = useRef<{ x: number; y: number; view: [number, number, number, number] } | null>(null);
  const projectFile = useRef<HTMLInputElement | null>(null);
  const levelFile = useRef<HTMLInputElement | null>(null);
  const source = useRef<HTMLInputElement | null>(null);
  const revision = useRef<HTMLInputElement | null>(null);
  const ready = useRef(false);
  const recovery = useRef<DesktopProject | null>(null);
  const desktopAnnounced = useRef(false);
  const [recoveryPending, setRecoveryPending] = useState(false);
  const p = state?.present;
  const dirty = !!p && JSON.stringify(p) !== saved;

  const call = useCallback(<T,>(operation: string, payload: unknown = {}): Promise<T> => new Promise((resolve, reject) => {
    if (!worker.current || !ready.current) { reject(new Error("Wait for the section engine to finish loading.")); return; }
    const id = ++sequence.current;
    requests.current.set(id, { resolve: value => resolve(JSON.parse(JSON.stringify(value, (_key, item) => item === undefined ? null : item)) as T), reject });
    worker.current.postMessage({ id, calculator: "typicals", operation, payload });
  }), []);

  useEffect(() => {
    const active = new Worker("/pyodide-worker.js");
    worker.current = active;
    const pending = requests.current;
    active.onmessage = ({ data }) => {
      if (data.type === "status") setStatus(data.message);
      if (data.type === "fatal") { setError(data.message); setStatus("Engine failed to load. Reload to retry."); }
      if (data.type === "response") {
        const request = pending.get(data.id); pending.delete(data.id);
        if (data.ok) request?.resolve(data.result); else request?.reject(new Error(data.error?.message || "Section operation failed."));
      }
      if (data.type === "ready") {
        ready.current = true; setStatus("Local section engine ready");
        void call<Project>("starter").then(value => { setState(history(value)); setSaved(JSON.stringify(value)); }).catch(e => setError(e.message));
      }
    };
    active.onerror = () => { setError("The section worker stopped. Save work if possible and reload."); pending.forEach(v => v.reject(new Error("Section worker stopped."))); pending.clear(); };
    active.postMessage({ calculator: "typicals", operation: "initialize" });
    return () => { active.terminate(); ready.current = false; pending.forEach(v => v.reject(new Error("Workspace closed."))); pending.clear(); };
  }, [call]);

  useEffect(() => {
    if (!p) return;
    let cancelled = false;
    void call<Scene>("draw", { project: p }).then(value => {
      if (!cancelled) { setScene(value); setView(current => current || [value.bounds[0], -value.bounds[3], value.bounds[2] - value.bounds[0], value.bounds[3] - value.bounds[1]]); }
    }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [p, call]);

  useEffect(() => {
    if (mode !== "print" || !p) return;
    let cancelled = false;
    void call<Export>("svg", { project: p }).then(value => { if (!cancelled) setSheet(new TextDecoder().decode(Uint8Array.from(atob(value.content_base64), c => c.charCodeAt(0)))); }).catch(e => { if (!cancelled) { setSheet(""); setError(e.message); } });
    return () => { cancelled = true; };
  }, [p, mode, call]);

  const edit = async (change: (value: Project) => void) => {
    if (!p || busy) return;
    setBusy(true); setError("");
    try {
      const next = structuredClone(p); change(next);
      const result = await call<Scene>("draw", { project: next });
      setState(current => current && commit(current, next)); setScene(result); setReport(null);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const download = async (name: string, bytes: Uint8Array, saveAs = true) => {
    if (desktop) return desktop.saveFile(name, bytes, saveAs);
    const url = URL.createObjectURL(new Blob([bytes as BlobPart]));
    const a = document.createElement("a"); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    return "saved";
  };
  const save = async (saveAs = false) => {
    if (!p || busy) return;
    setBusy(true); setError("");
    try {
      const value = await call<{ content: string }>("save", { project: p });
      if (await download("section.typicals.json", new TextEncoder().encode(value.content), saveAs) === "saved") { setSaved(JSON.stringify(p)); setStatus("Project saved. Save as a new name to keep a reusable full-section preset."); }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const open = async (file: DesktopProject, restoring = false) => {
    if (dirty && !restoring && !window.confirm("Discard unsaved changes and open this section?")) { if (file.token) await desktop?.projectOpened(file.token, false); return; }
    setBusy(true); setError("");
    try {
      const value = await call<Project>("load", { content: file.content });
      setState(history(value)); setSaved(restoring ? "" : JSON.stringify(value)); setView(null); setStatus(`Opened ${file.name}`);
      if (file.token) await desktop?.projectOpened(file.token, true);
      if (restoring) { await desktop?.resolveRecovery(true); recovery.current = null; setRecoveryPending(false); }
    } catch (e) { setError((e as Error).message); if (file.token) await desktop?.projectOpened(file.token, false); }
    finally { setBusy(false); }
  };
  const newSection = async () => {
    if (busy || (dirty && !window.confirm("Discard unsaved changes and start a generic rural section?"))) return;
    try { await desktop?.newProject(); const next = await call<Project>("starter"); setState(history(next)); setSaved(JSON.stringify(next)); setView(null); setError(""); } catch (e) { setError((e as Error).message); }
  };
  const exportFile = async (format: "pdf" | "svg" | "dxf") => {
    setBusy(true); setError("");
    try {
      const value = await call<Export>(format, { project: p });
      const binary = atob(value.content_base64); const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
      const result = await download(`typical-section.${format}`, bytes);
      if (result === "saved") { setStatus(`${format.toUpperCase()} exported`); if (value.report) setReport(value.report); }
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  useEffect(() => {
    if (!desktop) return;
    void desktop.workspaceState(dirty || recoveryPending, busy || !p).catch(e => setError(e.message));
    if (p && !recoveryPending) void desktop.saveRecovery(dirty ? JSON.stringify(p) : null).catch(e => setError(e.message));
  }, [desktop, dirty, busy, p, recoveryPending]);
  useEffect(() => {
    if (!desktop || !p || desktopAnnounced.current) return;
    desktopAnnounced.current = true;
    void desktop.ready().then(value => { recovery.current = value; setRecoveryPending(!!value); }).catch(e => setError(e.message));
  }, [desktop, p]);
  useEffect(() => {
    if (!desktop) return;
    const offProject = desktop.onProject(file => { void open(file); });
    const offMenu = desktop.onMenu(action => {
      if (action === "save" || action === "save-as") void save(action === "save-as");
      if (action === "new") void newSection();
      if (action === "updates") void desktop.updateState().then(value => setStatus(value.message || value.status));
    });
    return () => { offProject(); offMenu(); };
  });
  useEffect(() => {
    const beforeUnload = (e: BeforeUnloadEvent) => { if (dirty || busy || recoveryPending) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", beforeUnload);
    const key = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || busy || /INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName)) return;
      if (e.key.toLowerCase() === "z") { e.preventDefault(); setState(current => current && (e.shiftKey ? redo(current) : undo(current))); setError(""); }
      if (e.key.toLowerCase() === "s" && !desktop) { e.preventDefault(); void save(e.shiftKey); }
    };
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("beforeunload", beforeUnload); window.removeEventListener("keydown", key); };
  });

  const togglePointLock = (name: string, locked: boolean) => {
    if (!scene) return;
    const coordinates = scene.geometry.points[name];
    void edit(q => { if (locked) q.constraints.locked_points[name] = [coordinates[0], coordinates[1]]; else delete q.constraints.locked_points[name]; });
  };
  const fit = () => { if (scene) setView([scene.bounds[0], -scene.bounds[3], scene.bounds[2] - scene.bounds[0], scene.bounds[3] - scene.bounds[1]]); };
  const zoom = (factor: number) => setView(v => v && [v[0] + v[2] * (1 - factor) / 2, v[1] + v[3] * (1 - factor) / 2, v[2] * factor, v[3] * factor]);
  const coordinate = (e: React.PointerEvent<SVGSVGElement>): Point => {
    const svg = svgRef.current; const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return [0, 0];
    const q = new DOMPoint(e.clientX, e.clientY).matrixTransform(matrix.inverse());
    let value: Point = [q.x, -q.y];
    if (snapping && scene) {
      const nearest = Object.values(scene.geometry.points).sort((a, b) => Math.hypot(a[0] - value[0], a[1] - value[1]) - Math.hypot(b[0] - value[0], b[1] - value[1]))[0];
      if (nearest && Math.hypot(nearest[0] - value[0], nearest[1] - value[1]) < (view?.[2] || 100) / 50) value = nearest;
    }
    return value;
  };

  const visibleLevels = scene ? Object.entries(scene.styles).filter(([, style], index, entries) => style.name === "Unmapped" || entries.findIndex(([, other]) => other.name === style.name) === index) : [];
  return <main className={`typicals-app${desktop ? " typicals-desktop" : ""}`}>
    <header className="typicals-toolbar"><div><h1>VeriCivil Typicals</h1><span>Rural section designer · Preview{dirty ? " · Unsaved changes" : ""}</span></div><div className="typicals-actions">
      <button disabled={!p || busy || recoveryPending} onClick={() => void newSection()}>New section</button><button disabled={!p || busy || recoveryPending} onClick={() => desktop ? void desktop.openProjectDialog().catch(e => setError(e.message)) : projectFile.current?.click()}>Open…</button>
      <button disabled={!p || busy || recoveryPending} onClick={() => void save()}>Save project…</button><button disabled={!state?.past.length || busy} onClick={() => { setState(s => s && undo(s)); setError(""); }}>Undo</button><button disabled={!state?.future.length || busy} onClick={() => { setState(s => s && redo(s)); setError(""); }}>Redo</button>
    </div></header>
    <input hidden ref={projectFile} type="file" accept=".json,.vericivil" onChange={async e => { const file = e.target.files?.[0]; if (file) { if (file.size > 4 * 1024 * 1024) setError("Project exceeds 4 MiB."); else await open({ name: file.name, content: await file.text() }); } e.target.value = ""; }} />
    {recoveryPending && <div className="typicals-message">A local project recovery is available. <button disabled={!p || busy} onClick={() => recovery.current && void open(recovery.current, true)}>Restore recovery</button> <button onClick={() => { void desktop?.resolveRecovery(false).then(() => { recovery.current = null; setRecoveryPending(false); }); }}>Discard recovery</button></div>}
    {error && <div className="typicals-error" role="alert">{error} <button onClick={() => setError("")}>Dismiss</button></div>}
    <div className="typicals-layout"><aside className="typicals-inspector" aria-label="Section properties"><nav aria-label="Inspector pages">{["Section", "Materials", "Levels", "Sheet"].map(t => <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>{t}</button>)}</nav>
      {!p ? <p role="status">{status}</p> : <fieldset disabled={busy || recoveryPending}>
        {tab === "Section" && <><h2>Geometry</h2><p>Looking ahead. Positive slopes rise outward on either side. Inputs apply on Enter or leaving a field.</p>
          <label>Component<select value={selected} onChange={e => setSelected(e.target.value)}>{["left_lane", "right_lane", "left_shoulder", "right_shoulder", "left_slope", "right_slope", "CL", "ground"].map(n => <option key={n}>{n}</option>)}</select></label>
          <label>Coordinate foot definition<select value={p.units} onChange={e => void edit(q => { q.units = e.target.value; })}><option value="international_foot">International foot (0.3048 m)</option><option value="us_survey_foot">US survey foot (1200/3937 m)</option></select></label><p>Changing the foot definition reinterprets coordinate values; it does not convert them.</p>
          <div className="typicals-fields"><Numeric label="CL offset (ft)" value={p.origin[0]} onChange={n => void edit(q => { q.origin[0] = n; })} /><Numeric label="Plan grade (ft)" value={p.origin[1]} onChange={n => void edit(q => { q.origin[1] = n; })} /></div>
          {(["left", "right"] as const).map(side => <section key={side}><h3>{side === "left" ? "Left of centerline" : "Right of centerline"}</h3><div className="typicals-fields">{([["lane_width_ft", "Lane width (ft)"], ["lane_slope_pct", "Lane slope (%)"], ["shoulder_width_ft", "Shoulder width (ft)"], ["shoulder_slope_pct", "Shoulder slope (%)"], ["roadside_hv", "Roadside H:1V"], ["roadside_height_ft", "Roadside rise (ft)"]] as const).map(([key, label]) => <Numeric key={key} label={label} value={p[side][key]} onChange={n => void edit(q => { q[side][key] = n; })} />)}</div><label className="typicals-check"><input type="checkbox" checked={p[side].shoulder_paved} onChange={e => void edit(q => { q[side].shoulder_paved = e.target.checked; })} />Paved shoulder</label><p>Negative roadside rise: fill; positive: cut. Fixed height, no automatic ground intersection.</p></section>)}
          {/* eslint-disable-next-line react-hooks/refs -- Named-point data is immutable scene state; this handler runs on change, never during render. */}
          <h3>Named points / constraints</h3>{scene && Object.entries(scene.geometry.points).map(([name, namedPoint]) => <label className="typicals-point" key={name}><input type="checkbox" checked={!!p.constraints.locked_points[name]} onChange={e => togglePointLock(name, e.target.checked)} /><span>Lock {name}</span><code>{namedPoint.map(v => v.toFixed(3)).join(", ")}</code></label>)}
          <h3>Original ground</h3><label>Offset, elevation pairs (ft)<textarea key={JSON.stringify(p.ground)} defaultValue={p.ground.map(v => v.join(", ")).join("\n")} onBlur={e => { const value = e.target.value; void edit(q => { q.ground = value.trim().split(/\n/).map(row => row.split(",").map(Number) as Point); }); }} rows={6} /></label>
        </>}
        {tab === "Materials" && <><h2>Pavement structure</h2><p>Continuous across lanes and paved shoulders. Thickness is vertical, in international inches.</p>{p.layers.map((layer, i) => <section key={layer.id}><h3>Material {i + 1}</h3><label>Name<input key={layer.name} defaultValue={layer.name} onBlur={e => void edit(q => { q.layers[i].name = e.target.value; })} /></label><label>Material description<input key={layer.material} defaultValue={layer.material} onBlur={e => void edit(q => { q.layers[i].material = e.target.value; })} /></label><Numeric label="Thickness (in)" value={layer.thickness_in} onChange={n => void edit(q => { q.layers[i].thickness_in = n; })} /><button disabled={p.layers.length === 1} onClick={() => void edit(q => { q.layers.splice(i, 1); })}>Remove layer</button></section>)}<button disabled={p.layers.length >= 12} onClick={() => void edit(q => { q.layers.push({ id: `layer_${Date.now()}`, name: "New course", material: "Project-specified material", thickness_in: 4 }); })}>Add pavement layer</button><p>Save a project under a new name to reuse the complete section and its structure.</p></>}
        {tab === "Levels" && <><h2>Workspace catalog</h2><p>Import actual TS_ levels from Bentley. Indexed colors and line weights need explicit RGB and mm mappings. No workspace binaries or fonts are bundled.</p><label>Report source / library<input ref={source} placeholder="DGNLIB filename and ORD version" /></label><label>Workspace revision<input ref={revision} placeholder="Workspace version / report date" /></label><button onClick={() => levelFile.current?.click()}>Import level CSV / JSON…</button>
          <input hidden ref={levelFile} type="file" accept=".csv,.json" onChange={async e => { const file = e.target.files?.[0]; if (file) { try { if (file.size > 4 * 1024 * 1024) throw new Error("Level report exceeds 4 MiB."); const catalog = await call<Catalog>("import_levels", { content: await file.text(), source: source.current?.value || file.name, revision: revision.current?.value || "Unspecified revision" }); await edit(q => { q.catalog = catalog; }); } catch (err) { setError((err as Error).message); } } e.target.value = ""; }} />
          {p.catalog ? <p><strong>{p.catalog.extraction_status}</strong><br />{p.catalog.source}<br />Revision: {p.catalog.revision} · {p.catalog.levels.length} levels</p> : <p className="typicals-warning">No verified symbology imported. CAD colors are illustrative; DXF is blocked.</p>}
          {roles.map(role => <label key={role}>{role.replaceAll("_", " ")}<select value={p.level_mappings[role] || ""} onChange={e => void edit(q => { q.level_mappings[role] = e.target.value; })}><option value="">Unmapped — select TS_ level</option>{p.catalog?.levels.map(level => <option key={level.name} value={level.name}>{level.name}</option>)}</select></label>)}
          {p.catalog?.levels.map(level => <details key={level.name}><summary>{level.name}</summary><p>{level.description}</p><code>ByLevel: {level.bylevel_color ?? "?"} / {level.bylevel_weight ?? "?"} / {level.bylevel_style ?? "?"}<br />RGB {level.rgb ?? "unresolved"} · {level.lineweight_mm ?? "?"} mm<br />Dash: {JSON.stringify(level.dash_ft)}</code></details>)}
        </>}
        {tab === "Sheet" && <><h2>Drawing & sheet</h2>{(["title", "route", "construction", "stations"] as const).map(key => <label key={key}>{key}<input key={p.metadata[key]} defaultValue={p.metadata[key]} onBlur={e => void edit(q => { q.metadata[key] = e.target.value; })} /></label>)}<label>Notes (one per line)<textarea key={JSON.stringify(p.metadata.notes)} defaultValue={p.metadata.notes.join("\n")} onBlur={e => void edit(q => { q.metadata.notes = e.target.value.split("\n").filter(Boolean); })} /></label>
          <Numeric label="Scale: 1 in = feet" value={p.drafting.scale_ft_per_in} onChange={n => void edit(q => { q.drafting.scale_ft_per_in = n; })} /><Numeric label="Text height on paper (in)" value={p.drafting.text_height_in} onChange={n => void edit(q => { q.drafting.text_height_in = n; })} /><Numeric label="Dimension spacing on paper (in)" value={p.drafting.dimension_gap_in} onChange={n => void edit(q => { q.drafting.dimension_gap_in = n; })} /><Numeric label="Label decimal places" value={p.drafting.precision} onChange={n => void edit(q => { q.drafting.precision = n; })} />
          <label>Print / preview font<select value={p.drafting.font} onChange={e => void edit(q => { q.drafting.font = e.target.value; })}>{["Helvetica", "Courier", "Times-Roman"].map(font => <option key={font}>{font}</option>)}</select></label><div className="typicals-fields"><Numeric label="Sheet width (in)" value={p.print.width_in} onChange={n => void edit(q => { q.print.width_in = n; })} /><Numeric label="Sheet height (in)" value={p.print.height_in} onChange={n => void edit(q => { q.print.height_in = n; })} /></div><label className="typicals-check"><input type="checkbox" checked={p.print.monochrome} onChange={e => void edit(q => { q.print.monochrome = e.target.checked; })} />Monochrome print / vector exports</label><p>CAD level colors remain unchanged. Sheets that do not fit are rejected; increase ft/in or sheet size.</p>
          <h3>Print line weights</h3><p>Generic sheet hierarchy in mm; these settings do not change imported CAD ByLevel weights.</p>{roles.filter(role => !["dimension_text", "slopes", "text"].includes(role)).map(role => <Numeric key={role} label={`${role.replaceAll("_", " ")} (mm)`} value={p.print.lineweights_mm?.[role] ?? ({ surface: .5, pavement: .25, left_slope: .35, right_slope: .35, ground: .18, centerline: .13, dimensions: .13, callouts: .18 }[role] || .18)} onChange={n => void edit(q => { q.print.lineweights_mm = { ...q.print.lineweights_mm, [role]: n }; })} />)}
          <h3>Annotation override</h3><label>Drawing annotation<select value={selected} onChange={e => setSelected(e.target.value)}><option value={selected}>{selected}</option>{scene?.primitives.filter(v => v.kind === "text").map((v, i) => <option key={i} value={v.component}>{v.component}</option>)}</select></label><div className="typicals-fields">{([0, 1] as const).map(axis => <Numeric key={axis} label={`${axis === 0 ? "Horizontal" : "Vertical"} offset (ft)`} value={p.annotations[selected]?.[axis] || 0} onChange={n => void edit(q => { const pt: Point = [...q.annotations[selected] || [0, 0]] as Point; pt[axis] = n; q.annotations[selected] = pt; })} />)}</div><button onClick={() => void edit(q => { delete q.annotations[selected]; })}>Reset annotation position</button>
        </>}
      </fieldset>}
    </aside><section className="typicals-workspace" aria-label="Drawing workspace"><div className="typicals-viewbar"><div>{(["cad", "print"] as const).map(m => <button key={m} aria-pressed={mode === m} onClick={() => { setMode(m); setError(""); }}>{m === "cad" ? "Engineering CAD" : "Engineering print"}</button>)}</div><div><button onClick={() => zoom(.8)} disabled={mode !== "cad"}>Zoom in</button><button onClick={() => zoom(1.25)} disabled={mode !== "cad"}>Zoom out</button><button onClick={fit} disabled={mode !== "cad"}>Fit</button><button disabled={mode !== "cad"} aria-pressed={measure} onClick={() => { setMeasure(!measure); setMeasurePoints([]); }}>Measure</button><button disabled={mode !== "cad"} aria-pressed={snapping} onClick={() => setSnapping(!snapping)}>Point snap</button></div></div>
      {mode === "cad" && scene && view ? <svg ref={svgRef} className="typicals-canvas" viewBox={view.join(" ")} role="img" aria-label="Editable engineering section. Select elements; pan with middle mouse or Shift drag; scroll to zoom." onWheel={e => zoom(e.deltaY > 0 ? 1.1 : .9)} onPointerDown={e => { if (e.button === 1 || e.shiftKey) { e.preventDefault(); drag.current = { x: e.clientX, y: e.clientY, view }; e.currentTarget.setPointerCapture(e.pointerId); } else if (measure) setMeasurePoints(values => values.length === 2 ? [coordinate(e)] : [...values, coordinate(e)]); }} onPointerUp={() => { drag.current = null; }} onPointerMove={e => { const xy = coordinate(e); setCursor(xy); if (drag.current && svgRef.current) { const m = svgRef.current.getScreenCTM(); if (m) { const v = drag.current.view; setView([v[0] - (e.clientX - drag.current.x) / m.a, v[1] - (e.clientY - drag.current.y) / m.d, v[2], v[3]]); } } }}>
        <defs><pattern id="typicals-grid" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M 5 0 L 0 0 0 5" fill="none" stroke="#32443f" strokeWidth=".035" /></pattern></defs><rect x={view[0]} y={view[1]} width={view[2]} height={view[3]} fill="url(#typicals-grid)" />
        {scene.primitives.filter(item => !hidden.includes(scene.styles[item.role].name === "Unmapped" ? item.role : scene.styles[item.role].name)).map((item, i) => { const style = scene.styles[item.role]; const color = style.rgb; const common = { stroke: color, strokeWidth: style.lineweight_mm * 3, vectorEffect: "non-scaling-stroke", strokeDasharray: style.dash_ft.map(Math.abs).join(" "), onClick: () => { if (!measure) setSelected(item.component); } }; return <g key={i} className={selected === item.component ? "selected" : ""} data-component={item.component}>{item.kind === "line" && item.b ? <><line x1={item.a[0]} y1={-item.a[1]} x2={item.b[0]} y2={-item.b[1]} {...common} /><line x1={item.a[0]} y1={-item.a[1]} x2={item.b[0]} y2={-item.b[1]} stroke="transparent" strokeWidth="9" vectorEffect="non-scaling-stroke" onClick={common.onClick} /></> : item.kind === "circle" ? <circle cx={item.a[0]} cy={-item.a[1]} r={item.radius} fill="none" {...common} /> : item.kind === "polygon" ? <polygon points={item.points?.map(pt => `${pt[0]},${-pt[1]}`).join(" ")} fill={color} onClick={common.onClick} /> : <text x={item.a[0]} y={-item.a[1]} fontSize={item.height} textLength={item.text ? item.text_width : undefined} lengthAdjust="spacingAndGlyphs" transform={`rotate(${-Number(item.rotation || 0)} ${item.a[0]} ${-item.a[1]})`} fill={color} fontFamily={p?.drafting.font === "Courier" ? "monospace" : p?.drafting.font === "Times-Roman" ? "serif" : "sans-serif"} onClick={common.onClick}>{item.text}</text>}</g>; })}
        {measurePoints.map((pt, i) => <circle key={i} cx={pt[0]} cy={-pt[1]} r={view[2] / 250} fill="#ffffff" />)}{measurePoints.length === 2 && <line x1={measurePoints[0][0]} y1={-measurePoints[0][1]} x2={measurePoints[1][0]} y2={-measurePoints[1][1]} stroke="white" vectorEffect="non-scaling-stroke" strokeWidth="2" />}
      </svg> : mode === "print" ? <div className="typicals-sheet" aria-label="Vector engineering print preview">{sheet ? <div dangerouslySetInnerHTML={{ __html: sheet }} /> : <p>{error ? "Adjust sheet settings to show print preview." : "Preparing vector sheet…"}</p>}</div> : <div className="typicals-loading">{status}</div>}
      <div className="typicals-readout"><span>X {cursor[0].toFixed(3)} ft · Elev {cursor[1].toFixed(3)} ft</span><span>{selected}</span><span>{measurePoints.length === 2 ? `ΔX ${Math.abs(measurePoints[1][0] - measurePoints[0][0]).toFixed(3)} · ΔY ${(measurePoints[1][1] - measurePoints[0][1]).toFixed(3)} · Length ${Math.hypot(measurePoints[1][0] - measurePoints[0][0], measurePoints[1][1] - measurePoints[0][1]).toFixed(3)} ft` : "Middle mouse / Shift drag: pan · Scroll: zoom · Select a line to inspect"}</span></div>
      <div className="typicals-levelbar" aria-label="Drawing level visibility">{scene && visibleLevels.map(([role, style]) => <label key={role} title={`${style.name} · ${style.lineweight_mm} mm · ${style.resolved ? "Imported symbology" : "Illustrative preview"}`}><input type="checkbox" checked={!hidden.includes(style.name === "Unmapped" ? role : style.name)} onChange={e => { const key = style.name === "Unmapped" ? role : style.name; setHidden(values => e.target.checked ? values.filter(v => v !== key) : [...values, key]); }} /><i style={{ background: style.rgb }} />{style.name === "Unmapped" ? role : style.name}</label>)}</div>
      {scene?.warnings.length ? <details className="typicals-warnings"><summary>{scene.warnings.length} workspace issues · DXF requires resolved TS_ mappings</summary><ul>{scene.warnings.map(v => <li key={v}>{v}</li>)}</ul></details> : <p className="typicals-mapped">All roles mapped to imported TS_ levels. Confirm source report values in ORD.</p>}
      <footer className="typicals-exportbar"><span role="status">{busy ? "Updating section…" : status}</span><div>{(["dxf", "svg", "pdf"] as const).map(format => <button key={format} disabled={!p || busy || !!error || recoveryPending || (format === "dxf" && !!scene?.warnings.length)} onClick={() => void exportFile(format)}>Export {format.toUpperCase()}</button>)}</div></footer>
      {report && <details className="typicals-report" open><summary>DXF export report</summary><button onClick={() => void download("typical-section-report.txt", new TextEncoder().encode(JSON.stringify(report, null, 2))).then(result => { if (result === "saved") setStatus("DXF report saved"); }).catch(e => setError(e.message))}>Save export report…</button><pre>{JSON.stringify(report, null, 2)}</pre></details>}
    </section></div>
  </main>;
}
