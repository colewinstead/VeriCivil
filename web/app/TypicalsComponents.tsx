"use client";

import { useState } from "react";
import type { LibraryItem, Project, Point, SectionComponent } from "@/lib/typicals-types";

export function Numeric({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  return <label>{label}<input key={value} type="number" step="any" defaultValue={value} onBlur={e => { const draft = e.currentTarget.value; e.currentTarget.value = String(value); if (draft !== String(value)) onChange(draft.trim() ? Number(draft) : NaN); }} onKeyDown={e => { if (e.key === "Escape") e.currentTarget.value = String(value); if (e.key === "Enter" || e.key === "Escape") e.currentTarget.blur(); }} /></label>;
}

export default function TypicalsComponents({ project: p, library, selected, onSelect, onEdit, onImport, onSave }: {
  project: Project; library: LibraryItem[]; selected: string; onSelect: (id: string) => void;
  onEdit: (change: (project: Project) => void) => Promise<boolean>;
  onImport: (side: "left" | "right") => void; onSave: (component: SectionComponent) => void;
}) {
  const [kind, setKind] = useState({ left: "lane", right: "lane" });
  const [viewSide, setViewSide] = useState<"left" | "right">("left");
  const selectedSide = p.left.some(c => c.id === selected) ? "left" : p.right.some(c => c.id === selected) ? "right" : null;
  const activeSide = selectedSide || viewSide;
  const component = selectedSide ? p[selectedSide].find(c => c.id === selected) : null;
  const definition = library.find(v => v.kind === component?.kind);
  const update = (change: (component: SectionComponent) => void) => onEdit(q => { const c = [...q.left, ...q.right].find(c => c.id === selected); if (c) change(c); });
  const add = async (side: "left" | "right", duplicate = false) => {
    const source = duplicate && component ? component : library.find(item => item.kind === kind[side])?.template;
    if (!source) return;
    const value = structuredClone(source);
    value.id = `${side}_${source.kind}_${crypto.randomUUID().slice(0, 8)}`;
    value.end_point = value.id;
    if (duplicate) value.name += " copy";
    const accepted = await onEdit(q => {
      const items = q[side];
      let index = items.findIndex(c => c.id === selected);
      if (index < 0) {
        if (["lane", "auxiliary_lane"].includes(value.kind)) index = items.findLastIndex(c => ["lane", "auxiliary_lane"].includes(c.kind));
        else if (value.kind !== "median") { const roadside = items.findIndex(c => ["slope", "ditch", "retaining_wall"].includes(c.kind)); index = (roadside < 0 ? items.length : roadside) - 1; }
      }
      items.splice(index + 1, 0, value);
      if (duplicate && q.level_mappings["component:" + selected]) q.level_mappings["component:" + value.id] = q.level_mappings["component:" + selected];
    });
    if (accepted) onSelect(value.id);
  };
  const move = (direction: number) => {
    if (!selectedSide) return;
    void onEdit(q => {
      const items = q[selectedSide]; const index = items.findIndex(c => c.id === selected);
      const target = index + direction;
      if (target >= 0 && target < items.length) [items[index], items[target]] = [items[target], items[index]];
    });
  };
  const remove = async () => {
    if (!selectedSide) return;
    const accepted = await onEdit(q => { q[selectedSide] = q[selectedSide].filter(c => c.id !== selected); delete q.level_mappings["component:" + selected]; });
    if (accepted) { setViewSide(selectedSide); onSelect("CL"); }
  };

  return <div className="typicals-component-editor"><h2>Section components</h2><p>Select a component to edit it. Add after the selection; move items to change their connections.</p>
    <div className="typicals-side-switch" role="group" aria-label="Roadway side">{(["left", "right"] as const).map(side => <button key={side} aria-pressed={activeSide === side} onClick={() => { setViewSide(side); onSelect(p[side][0]?.id || "CL"); }}>{side === "left" ? "Left" : "Right"} ({p[side].length})</button>)}</div>
    {[activeSide].map(side => <section className="typicals-component-side" key={side}><div className="typicals-component-heading"><h3>{side === "left" ? "Left of centerline" : "Right of centerline"}</h3><span>Inside → outside</span></div>
      <ol className="typicals-component-list" aria-label={`${side} components`}>{p[side].map((c, index) => <li key={c.id}><button type="button" aria-pressed={selected === c.id} onClick={() => onSelect(c.id)} aria-label={`Select ${c.name} on ${side}`}><span className="typicals-component-order">{index + 1}</span><span><strong>{c.name}</strong><small>{library.find(v => v.kind === c.kind)?.label || c.kind}{c.params.width_ft !== undefined ? ` · ${c.params.width_ft} ft` : ""}</small></span></button></li>)}</ol>
      <div className="typicals-add-component"><select aria-label={`Add ${side} component type`} value={kind[side]} onChange={e => setKind(values => ({ ...values, [side]: e.target.value }))}>{library.map(item => <option key={item.kind} value={item.kind}>{item.label}</option>)}</select><button type="button" onClick={() => void add(side)} aria-label={`Add component to ${side}`}>Add</button></div>
      <button className="typicals-preset-button" onClick={() => onImport(side)}>Import component preset…</button>
    </section>)}
    {component && selectedSide && definition ? <section className="typicals-component-properties" aria-label="Selected component properties"><h3>{component.name}</h3><div className="typicals-component-actions"><button aria-label="Move component inward" disabled={p[selectedSide][0].id === selected} onClick={() => move(-1)}>Inward</button><button aria-label="Move component outward" disabled={p[selectedSide][p[selectedSide].length - 1].id === selected} onClick={() => move(1)}>Outward</button><button onClick={() => void add(selectedSide, true)}>Duplicate</button><button onClick={() => void remove()}>Remove</button></div>
      <label>Component name<input key={component.id + component.name} defaultValue={component.name} onBlur={e => { const value = e.currentTarget.value; e.currentTarget.value = component.name; void update(c => { c.name = value; }); }} /></label>
      <div className="typicals-fields">{Object.entries(definition.fields).map(([key, field]) => <Numeric key={component.id + key} label={field.label} value={component.params[key]} onChange={n => void update(c => { c.params[key] = n; })} />)}</div>
      {definition.paved !== undefined && <label className="typicals-check"><input type="checkbox" checked={component.paved} onChange={e => { const checked = e.target.checked; void update(c => { c.paved = checked; }); }} />Apply pavement structure</label>}
      {component.kind === "custom" && <label>Profile points: outward offset, rise (ft)<textarea key={component.id + JSON.stringify(component.points)} rows={6} defaultValue={component.points?.map(pt => pt.join(", ")).join("\n")} onBlur={e => { const content = e.currentTarget.value; void update(c => { c.points = content.trim().split("\n").map(row => row.split(",").map(value => value.trim() ? Number(value) : NaN) as Point); }); }} /><small>Start at 0, 0. The last point connects the next component. Non-paved profiles can close or overhang; paved profiles need increasing outward offsets.</small></label>}
      {["barrier", "guardrail", "retaining_wall", "curb_gutter"].includes(component.kind) && <p>Generic editable profile. Confirm the shape and dimensions against project details; no structural or crashworthiness design is performed.</p>}
      <label>Component CAD level<select value={p.level_mappings["component:" + component.id] || ""} onChange={e => { const value = e.target.value; void onEdit(q => { if (value) q.level_mappings["component:" + component.id] = value; else delete q.level_mappings["component:" + component.id]; }); }}><option value="">Use category mapping</option>{p.catalog?.levels.map(level => <option value={level.name} key={level.name}>{level.name}</option>)}</select></label>
      <label>Named end point<input key={component.id + component.end_point} defaultValue={component.end_point} onBlur={e => { const value = e.currentTarget.value; e.currentTarget.value = component.end_point; void update(c => { c.end_point = value; }); }} /></label>
      <button onClick={() => onSave(component)}>Save component preset…</button><p>Presets store geometry and properties. CAD levels remain project-specific.</p>
    </section> : <p>Select a component in the list or drawing to edit its dimensions and properties.</p>}
  </div>;
}
