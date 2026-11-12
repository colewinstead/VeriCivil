"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import manifest from "./generated/guardrail.json";
import "./guardrail.css";

type Values = typeof manifest.defaults;
type Field = keyof Values;
type Calculation = {
  results: Record<string, number>;
  roadway: { L2_opp: number; added_distance: number };
  LA: number; L1: number; terminal: number;
  engine_version: string; source_commit: string; limitations: string;
};
type Download = { filename: string; mime: string; content: string | Uint8Array };
type Loaded = { values: Values; calculation: Calculation; engine_changed: boolean };

function download(file: Download) {
  const url = URL.createObjectURL(new Blob([file.content as BlobPart], { type: file.mime }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const format = (value: number) => value.toLocaleString("en-US", { minimumFractionDigits: 4, maximumFractionDigits: 4 });

export default function GuardrailCalculator() {
  const [values, setValues] = useState<Values>(manifest.defaults);
  const [baseline, setBaseline] = useState(JSON.stringify(manifest.defaults));
  const [runtime, setRuntime] = useState<"loading" | "ready" | "error">("loading");
  const [status, setStatus] = useState("Loading the browser calculation engine…");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [calculation, setCalculation] = useState<{ signature: string; data: Calculation } | null>(null);
  const worker = useRef<Worker | null>(null);
  const pending = useRef(new Map<number, { resolve(value: unknown): void; reject(error: Error): void }>());
  const nextId = useRef(0);
  const latest = useRef(values);
  const fileInput = useRef<HTMLInputElement>(null);
  const signature = JSON.stringify(values);
  const dirty = signature !== baseline;
  const result = calculation?.signature === signature ? calculation.data : null;
  const divided = values.facility === "divided_highway";
  const clearzone = values.offset_source === "clearzone";
  const threeR = values.clear_zone_criteria === "3r";

  const request = useCallback(<T,>(operation: string, payload: object): Promise<T> => {
    const id = ++nextId.current;
    return new Promise<unknown>((resolve, reject) => {
      if (!worker.current) { reject(new Error("Reload the page to restart the calculation engine.")); return; }
      pending.current.set(id, { resolve, reject });
      worker.current.postMessage({ id, calculator: "guardrail", operation, payload });
    }).then(value => value as T);
  }, []);

  useEffect(() => {
    const instance = new Worker("/pyodide-worker.js");
    worker.current = instance;
    const requests = pending.current;
    const fail = (message: string) => {
      setRuntime("error"); setStatus(message);
      requests.forEach(({ reject }) => reject(new Error(message))); requests.clear();
    };
    instance.onmessage = ({ data }) => {
      if (data.type === "status") setStatus(data.message);
      if (data.type === "ready") {
        if (data.manifest.source_commit !== manifest.source_commit) {
          fail("The engine version changed. Reload this page before calculating."); return;
        }
        setRuntime("ready"); setStatus("Python engine ready · processing locally");
      }
      if (data.type === "fatal") fail(data.message || "Engine unavailable. Reload the page to try again.");
      if (data.type === "response") {
        const item = requests.get(data.id);
        requests.delete(data.id);
        if (data.ok) item?.resolve(data.result);
        else item?.reject(new Error(data.error?.message || "Operation failed. Try again."));
      }
    };
    instance.onerror = () => fail("Engine unavailable. Reload the page to try again.");
    instance.postMessage({ calculator: "guardrail", operation: "initialize" });
    return () => {
      requests.forEach(({ reject }) => reject(new Error("Calculator closed.")));
      requests.clear(); instance.terminate(); worker.current = null;
    };
  }, []);

  useEffect(() => {
    if (runtime !== "ready") return;
    let active = true;
    const timer = setTimeout(() => {
      request<Calculation>("calculate", { values }).then(data => {
        if (active) { setCalculation({ signature, data }); setError(""); }
      }).catch(reason => { if (active) { setCalculation(null); setError(reason.message); } });
    }, 350);
    return () => { active = false; clearTimeout(timer); };
  }, [request, runtime, signature, values]);

  useEffect(() => {
    if (!dirty) return;
    const navigation = (window as Window & { navigation?: { currentEntry?: { index: number } } }).navigation;
    let previousIndex = navigation?.currentEntry?.index;
    let restoring = false;
    const beforeHistory = (event: PopStateEvent) => {
      const currentIndex = navigation?.currentEntry?.index;
      if (restoring) { restoring = false; event.stopImmediatePropagation(); return; }
      if (previousIndex === undefined || currentIndex === undefined || previousIndex === currentIndex) return;
      if (window.confirm("Leave without saving your Guardrail project? Unsaved changes will be lost.")) {
        previousIndex = currentIndex; return;
      }
      // Restore the traversed history entry before the client router discards the form.
      event.stopImmediatePropagation(); restoring = true; history.go(previousIndex - currentIndex);
    };
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const beforeLink = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest("a[href]");
      if (!anchor || anchor.hasAttribute("download") || anchor.getAttribute("target") === "_blank" || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      if (!window.confirm("Leave without saving your Guardrail project? Unsaved changes will be lost.")) {
        event.preventDefault(); event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("popstate", beforeHistory, true);
    document.addEventListener("click", beforeLink, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener("popstate", beforeHistory, true);
      document.removeEventListener("click", beforeLink, true);
    };
  }, [dirty]);

  function update(name: Field, value: string) {
    const next = { ...latest.current, [name]: value };
    latest.current = next; setValues(next); setError(""); setNotice("");
  }

  async function exportFile(operation: "export_pdf" | "project_save") {
    setBusy(true); setError(""); setNotice("");
    const submitted = latest.current;
    try {
      const file = await request<Download>(operation, { values: submitted });
      if (latest.current !== submitted) throw new Error("Inputs changed. Review the current results and download again.");
      download(file);
      if (operation === "project_save") setBaseline(JSON.stringify(submitted));
      setNotice(operation === "project_save" ? "Project download started. Keep the JSON file to reopen these inputs." : "PDF download started. Review the calculation sheet before use.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Download failed. Try again."); }
    finally { setBusy(false); }
  }

  async function openProject(file: File) {
    setBusy(true); setError(""); setNotice("");
    try {
      if (file.size > 64 * 1024) throw new Error("Choose a Guardrail JSON project smaller than 64 KiB.");
      const loaded = await request<Loaded>("project_load", { content: await file.text() });
      if (dirty && !window.confirm("Replace your unsaved Guardrail inputs with this project?")) return;
      const nextSignature = JSON.stringify(loaded.values);
      latest.current = loaded.values; setValues(loaded.values); setBaseline(nextSignature);
      setCalculation({ signature: nextSignature, data: loaded.calculation });
      setNotice(loaded.engine_changed ? "Project reopened and recalculated with the currently bundled engine. Its source revision differs from the saved project; review the results." : "Project reopened and recalculated. Saved result numbers are never reused.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not open this project. Your inputs are unchanged."); }
    finally { setBusy(false); if (fileInput.current) fileInput.current.value = ""; }
  }

  function field(name: Field, label: string, unit?: string, props: { type?: string; hint?: string; readOnly?: boolean } = {}) {
    return <label className="guardrail-field" key={name}><span>{label}{unit && <small>{unit}</small>}</span><input name={name} type={props.type || "text"} inputMode={unit ? "decimal" : undefined} value={values[name]} onChange={event => update(name, event.target.value)} readOnly={props.readOnly} autoComplete="off" aria-describedby={props.hint ? `${name}-hint` : undefined} />{props.hint && <small id={`${name}-hint`}>{props.hint}</small>}</label>;
  }

  function select(name: Field, label: string, options: readonly (readonly [string, string])[]) {
    return <label className="guardrail-field" key={name}><span>{label}</span><select name={name} value={values[name]} onChange={event => update(name, event.target.value)}>{options.map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></label>;
  }

  return <main className="guardrail-shell">
    <header className="guardrail-header">
      <div><h1>Guardrail <span>Length of Need</span></h1><p>Review near-side and opposing-side lengths, then carry the calculation into a PDF. Free to use; calculations and project files stay in this browser.</p></div>
      <p className={`guardrail-runtime ${runtime}`} role="status">{status}</p>
    </header>
    <div className="guardrail-toolbar" aria-label="Project files">
      <button type="button" disabled={runtime !== "ready" || busy} onClick={() => fileInput.current?.click()}>Open project…</button>
      <input ref={fileInput} className="guardrail-file-input" type="file" accept=".json,application/json" aria-label="Open Guardrail project file" onChange={event => { const file = event.target.files?.[0]; if (file) void openProject(file); }} />
      <button type="button" disabled={!result || runtime !== "ready" || busy} onClick={() => void exportFile("project_save")}>Save project…</button>
      <span>{dirty ? "Unsaved changes" : "Inputs unchanged"}</span><small>Engine {manifest.calculation_engine_version} · feet / mph</small>
    </div>
    <div className="guardrail-messages">
      {error && <p className="guardrail-error" role="alert">{error}</p>}
      <p role="status">{busy ? "Preparing your file…" : notice}</p>
    </div>
    <div className="guardrail-workspace">
      <form onSubmit={event => event.preventDefault()} aria-label="Guardrail inputs">
        <fieldset disabled={busy} className="guardrail-inputs">
          <legend className="sr-only">Calculation inputs</legend>
          <section><h2>Roadway &amp; traffic</h2><div className="guardrail-fields">
            {select("facility", "Facility", [["two_lane_two_way", "Two-lane, two-way"], ["divided_highway", "Divided highway"]])}
            {select("speed", "Design speed (mph)", manifest.speeds.map(speed => [String(speed), String(speed)]))}
            {field("adt", "Design ADT", "vehicles/day", { hint: "Grouped thousands are accepted, for example 6,000." })}
            {field("lane_width", "Lane width", "ft")}
            {field("L2", "Near-side barrier offset, L2", "ft")}
            {divided && <>
              {field("lanes_this", "Lanes this direction", "lanes")}
              {field("lanes_opposing", "Lanes opposing", "lanes")}
              {field("median_width", "Median width", "ft")}
              {select("opposing_distance_mode", "Opposing crossing distance", [["manual", "Enter a custom distance"], ["calculated", "Use calculated distance"]])}
              {values.opposing_distance_mode === "manual" && field("added_distance", "Added opposing distance", "ft", { hint: "Added to L2. A custom crossing is used for calculation and PDF only." })}
            </>}
          </div><p className="guardrail-help">{divided ? "Calculated crossing uses both directions’ lane counts, lane width, and median width." : "Opposing offset is L2 plus one lane width."} {result && <>Opposing L2 used: <strong>{format(result.roadway.L2_opp)} ft</strong>.</>}</p></section>
          <section><h2>Hazard &amp; barrier</h2><div className="guardrail-fields">
            {select("offset_source", "Hazard offset source", [["clearzone", "Select from clear-zone table"], ["direct", "Enter LA directly"]])}
            {clearzone ? <>
              {select("clear_zone_criteria", "Clear-zone criteria", [["new_construction", "New construction · Table 9-2-A"], ["3r", "3R rural non-freeway · Table 12-2-B"]])}
              {select("slope", "Roadside slope", [["6:1_or_flatter", "6:1 or flatter"], ["5:1_to_4:1", "5:1 to 4:1"]])}
              {select("clear_zone_selection", "Clear-zone selection", [["min", "Minimum"], ["mid", "Midpoint"], ["max", "Maximum"], ["custom", "Custom"]])}
              {values.clear_zone_selection === "custom" && field("custom_clear_zone", "Custom clear zone", "ft")}
            </> : field("LA", "Hazard extent / offset, LA", "ft")}
            {select("L1_mode", "Transition length, L1", [["standard", "Standard · 18′-1.75″"], ["custom", "Custom length"]])}
            {values.L1_mode === "custom" && field("L1", "Custom L1", "ft")}
            {select("terminal_mode", "Terminal section", [["default", "Default · 25 ft"], ["custom", "Custom length"]])}
            {values.terminal_mode === "custom" && field("terminal", "Custom terminal section", "ft")}
            {select("flare_rate", "Flare rate (a:b)", manifest.flare_rates.map(rate => [String(rate), rate === 0 ? "Non-flared" : `${rate}:1`]))}
          </div>
          {clearzone && threeR && (
            <p className="guardrail-help">3R applies to recoverable fill slopes on non-curbed rural non-freeways where Chapter 9 is infeasible. Supported design speeds are 30–65 mph. The starred 15-ft allowance requires project review and is not applied automatically.</p>
          )}
          <p className="guardrail-help">{result ? <>LA used: <strong>{format(result.LA)} ft</strong> · L1: {format(result.L1)} ft · Terminal: {format(result.terminal)} ft</> : "Complete the active fields to calculate. Lengths are entered in decimal feet."}</p></section>
          <details className="guardrail-project"><summary>Project details <span>Optional · included in the PDF</span></summary><div className="guardrail-fields">
            {field("project", "Project")}{field("route_location", "Route / location")}{field("job_number", "Job number")}
            {field("prepared_by", "Prepared by")}{field("checked_by", "Checked by")}{field("calculation_date", "Calculation date", undefined, { type: "date", hint: "Uses the generation date when blank." })}
          </div></details>
          <p className="guardrail-help">Results update after you pause typing. Saving a project includes its inputs, selections, and PDF settings. Reopening validates and recalculates them.</p>
        </fieldset>
      </form>
      <aside className="guardrail-review" aria-labelledby="guardrail-results">
        <h2 id="guardrail-results">Length review</h2>
        {result ? <>
          <p className="guardrail-help">The same accepted inputs supply the results and calculation sheet.</p>
          <table className="guardrail-results"><caption>Calculated lengths in feet</caption><thead><tr><th scope="col">Length</th><th scope="col">Near side</th><th scope="col">Opposing</th></tr></thead><tbody>
            {([
              ["Runout, LR", "LR", "LR"], ["Minimum X", "X_min_near", "X_min_opp"],
              ["Required rail, B / D", "B_required", "D_required"], ["Rounded rail, B / D", "B", "D"],
              ["Overall, A / C", "A", "C"], ["Including gating", "A_plus_gating", "C_plus_gating"],
            ] as const).map(([label, near, opposing]) => <tr key={label}><th scope="row">{label}</th><td>{format(result.results[near])}</td><td>{format(result.results[opposing])}</td></tr>)}
          </tbody></table>
        </> : <div className="guardrail-empty"><h3>{runtime === "error" ? "Reload to restart the engine" : runtime === "loading" ? "Preparing local calculations" : "Review the active inputs"}</h3><p>{runtime === "loading" ? "The Python engine runs on your device. Initial loading needs an internet connection." : error || "Updated results appear here after the inputs are accepted. Old results are hidden when inputs change."}</p></div>}
        <fieldset className="guardrail-pdf" disabled={busy}><legend>Calculation PDF</legend>
          {select("pdf_style", "Package content", [["1", "Summary calculation sheet"], ["2", "Detailed calculations"], ["3", "Complete calculation package"]])}
          <label className="guardrail-checkbox"><input type="checkbox" checked={values.include_appendices === "yes"} onChange={event => update("include_appendices", event.target.checked ? "yes" : "no")} /><span>Append MDOT reference documents<small>Roadway manual + {divided ? "GR-4" : "GR-4a"}, selected for this facility. {clearzone && threeR && "For 3R, obtain the Table 12-2-B source page separately."}</small></span></label>
          <button type="button" className="primary" disabled={!result || runtime !== "ready" || busy} onClick={() => void exportFile("export_pdf")}>Download calculation PDF</button>
        </fieldset>
        <section className="guardrail-method"><h3>Source &amp; applicability</h3><p>{manifest.references.TABLE_9_6_A}. {clearzone ? manifest.references[threeR ? "TABLE_12_2_B" : "TABLE_9_2_A"] : "LA is entered directly."}</p><p>{manifest.limitations}</p><a href={`https://github.com/colewinstead/Guardrail-Calculator/tree/${manifest.source_commit}`} target="_blank" rel="noreferrer">Guardrail {manifest.calculation_engine_version} · source {manifest.source_commit.slice(0, 7)}</a></section>
      </aside>
    </div>
  </main>;
}
