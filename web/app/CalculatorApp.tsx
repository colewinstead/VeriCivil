"use client";

/* Browser worker responses mirror dynamically typed Python dictionaries. */
/* eslint-disable @typescript-eslint/no-explicit-any, @next/next/no-html-link-for-pages */

import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  allows,
  CAPABILITIES,
  CommercialPlan,
  EMPTY_FREE_ENTITLEMENT,
  EntitlementSnapshot,
  isLocalEntitlementDevelopment,
  LocalDevelopmentEntitlementProvider,
  localSnapshot,
  RemoteEntitlementProvider,
} from "./entitlements";
import SuperelevationAnalysis from "./SuperelevationAnalysis";
import UpgradeNotice from "./UpgradeNotice";
import { trackCalculatorEvent } from "@/lib/analytics/client";

type Dict = Record<string, any>;
type RuntimeState = "loading" | "ready" | "error";
type WritableFile = { write(data: Blob): Promise<void>; close(): Promise<void> };
type SaveFileHandle = { createWritable(): Promise<WritableFile> };
type SaveTarget = SaveFileHandle | "download";
const AUTO_CALC_DELAY_MS = 450;

const EXPORT_DETAILS: Record<string, { suffix: string; description: string }> = {
  export_pdf: { suffix: "-report", description: "PDF calculation report" },
  export_ord_csv: { suffix: "-ord", description: "OpenRoads superelevation CSV" },
  export_overlay_dxf: { suffix: "-overlay", description: "LandXML overlay DXF" },
};

const INITIAL_INPUTS: Dict = {
  criteria_profile: "mdot-rdsd-2026-04-22",
  project_name: "",
  route_name: "",
  alignment_name: "",
  curve_name: "",
  curve_direction: "left",
  pc: "",
  pt: "",
  speed: "",
  radius: "",
  facility: "centerline",
  area: "rural",
  lane_width: "12",
  lanes_rotated: "2",
  e_manual: "",
  friction: "",
  rel_grad: "",
  normal_crown: "0.02",
  Lr_manual: "",
  Lt_manual: "",
  station_equations: "",
  alignment_station_range: "",
  curve_notes: "",
  station_format: true,
};

function download(name: string, value: string | Uint8Array, type: string) {
  const blob = new Blob([value as BlobPart], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function chooseSaveTarget(name: string, type: string, extension: string, description: string): Promise<SaveTarget | null> {
  const picker = (window as Window & {
    showSaveFilePicker?: (options: Dict) => Promise<SaveFileHandle>;
  }).showSaveFilePicker;
  if (!picker) return "download";
  try {
    return await picker.call(window, {
      suggestedName: name,
      types: [{ description, accept: { [type]: [`.${extension}`] } }],
    });
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === "AbortError") return null;
    if (reason instanceof DOMException && ["SecurityError", "NotAllowedError"].includes(reason.name)) return "download";
    throw reason;
  }
}

async function saveExport(target: SaveTarget, name: string, value: string | Uint8Array, type: string) {
  if (target === "download") {
    download(name, value, type);
    return "downloaded";
  }
  const writable = await target.createWritable();
  await writable.write(new Blob([value as BlobPart], { type }));
  await writable.close();
  return "saved";
}

function cleanName(value: string, fallback: string) {
  const cleaned = value.trim().replace(/[^a-z0-9_-]+/gi, "-").replace(/^-+|-+$/g, "");
  return cleaned || fallback;
}

function calculationInputKey(inputs: Dict) {
  return JSON.stringify({
    criteria_profile: inputs.criteria_profile,
    curve_direction: inputs.curve_direction,
    pc: inputs.pc,
    pt: inputs.pt,
    speed: inputs.speed,
    radius: inputs.radius,
    facility: inputs.facility,
    area: inputs.area,
    lane_width: inputs.lane_width,
    lanes_rotated: inputs.lanes_rotated,
    e_manual: inputs.e_manual,
    friction: inputs.friction,
    rel_grad: inputs.rel_grad,
    normal_crown: inputs.normal_crown,
    Lr_manual: inputs.Lr_manual,
    Lt_manual: inputs.Lt_manual,
    station_equations: inputs.station_equations,
    alignment_station_range: inputs.alignment_station_range,
    station_format: inputs.station_format,
  });
}

export default function CalculatorApp() {
  const workerRef = useRef<Worker | null>(null);
  const entitlementProviderRef = useRef<{ refresh(): Promise<EntitlementSnapshot> } | null>(null);
  const pendingRef = useRef(new Map<number, { resolve: (value: any) => void; reject: (reason: Error) => void }>());
  const requestId = useRef(0);
  const calculationSequence = useRef(0);
  const loadedCurveCalculation = useRef<{ key: string; request: number } | null>(null);
  const lastTrackedCalculation = useRef("");
  const lastTrackedFailure = useRef("");
  const [runtime, setRuntime] = useState<RuntimeState>("loading");
  const [runtimeMessage, setRuntimeMessage] = useState("Starting private browser workspace…");
  const [progress, setProgress] = useState(4);
  const [manifest, setManifest] = useState<Dict | null>(null);
  const [entitlement, setEntitlement] = useState<EntitlementSnapshot>(EMPTY_FREE_ENTITLEMENT);
  const [upgradeFeature, setUpgradeFeature] = useState("");
  const [localDevelopment, setLocalDevelopment] = useState(false);
  const [inputs, setInputs] = useState<Dict>(INITIAL_INPUTS);
  const [calculation, setCalculation] = useState<Dict | null>(null);
  const [curves, setCurves] = useState<Dict[]>([]);
  const [selectedCurve, setSelectedCurve] = useState(-1);
  const [landxml, setLandxml] = useState<Dict | null>(null);
  const [landxmlPreset, setLandxmlPreset] = useState(0);
  const [excludedCurveIndexes, setExcludedCurveIndexes] = useState<number[]>([]);
  const [reverseCurvePairs, setReverseCurvePairs] = useState<number[][]>([]);
  const [calculationRequest, setCalculationRequest] = useState(0);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [lookupStation, setLookupStation] = useState("");
  const [lookupSlope, setLookupSlope] = useState("");
  const [lookupResult, setLookupResult] = useState<Dict | null>(null);
  const [corridorDiagram, setCorridorDiagram] = useState<Dict | null>(null);
  const [diagramInspector, setDiagramInspector] = useState<Dict | null>(null);
  const [corridorQa, setCorridorQa] = useState<Dict | null>(null);
  const [planView, setPlanView] = useState<Dict | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [dirty, setDirty] = useState(false);
  useEffect(() => trackCalculatorEvent("superelevation", "calculator_opened"), []);
  const startWorker = useCallback(() => {
    workerRef.current?.terminate();
    pendingRef.current.forEach(({ reject }) => reject(new Error("Browser workspace restarted.")));
    pendingRef.current.clear();
    setRuntime("loading");
    setProgress(4);
    const worker = new Worker("/pyodide-worker.js");
    workerRef.current = worker;
    worker.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === "status") {
        setRuntimeMessage(message.message);
        setProgress(message.progress || 0);
      } else if (message.type === "ready") {
        setRuntime("ready");
        setManifest(message.manifest);
        if (message.manifest?.commercial) {
          const provider = isLocalEntitlementDevelopment()
            ? new LocalDevelopmentEntitlementProvider(message.manifest.commercial)
            : new RemoteEntitlementProvider(message.manifest.commercial);
          entitlementProviderRef.current = provider;
          provider.getSnapshot().then(setEntitlement);
          setLocalDevelopment(isLocalEntitlementDevelopment());
        }
      } else if (message.type === "fatal") {
        setRuntime("error");
        setRuntimeMessage(message.message);
      } else if (message.type === "response") {
        const pending = pendingRef.current.get(message.id);
        if (!pending) return;
        pendingRef.current.delete(message.id);
        if (message.ok) {
          pending.resolve(message.result);
        } else {
          pending.reject(new Error(message.error?.message || "Operation failed."));
        }
      }
    };
    worker.postMessage({ calculator: "superelevation", operation: "initialize" });
  }, []);

  useEffect(() => {
    startWorker();
    return () => workerRef.current?.terminate();
  }, [startWorker]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  useEffect(() => {
    const refresh = () => entitlementProviderRef.current?.refresh().then(setEntitlement);
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, []);

  const call = useCallback((operation: string, payload: Dict = {}) => {
    if (!workerRef.current || runtime !== "ready") return Promise.reject(new Error("The browser workspace is not ready yet."));
    const id = ++requestId.current;
    return new Promise<any>((resolve, reject) => {
      pendingRef.current.set(id, { resolve, reject });
      workerRef.current!.postMessage({ id, calculator: "superelevation", operation, payload: { ...payload, entitlement } });
    });
  }, [runtime, entitlement]);

  const requestCapability = useCallback((capability: string) => {
    if (allows(entitlement, capability)) return true;
    setUpgradeFeature(manifest?.commercial?.capabilities?.[capability]?.name || "This feature");
    return false;
  }, [entitlement, manifest]);

  const proChip = (capability: string) => allows(entitlement, capability)
    ? null
    : <span className="pro-chip">Pro</span>;

  const changeDevelopmentEntitlement = (plan: CommercialPlan) => {
    if (!manifest?.commercial) return;
    entitlementProviderRef.current = new LocalDevelopmentEntitlementProvider(manifest.commercial, plan);
    setEntitlement(localSnapshot(manifest.commercial, plan));
    setNotice(`Local development entitlement changed to ${plan.toUpperCase()}.`);
  };

  const update = (key: string, value: any) => {
    setInputs((current) => ({ ...current, [key]: value }));
    setDirty(true);
  };

  const updateCriteriaProfile = (profileId: string) => {
    if (!profileId.startsWith("mdot") && !requestCapability(CAPABILITIES.allDotProfiles)) return;
    const tdot = profileId.startsWith("tdot");
    setInputs((current) => ({
      ...current,
      criteria_profile: profileId,
      facility: tdot ? "undivided" : "centerline",
      area: tdot && current.area === "local" ? "rural" : current.area,
      speed: "",
    }));
    setCalculation(null);
    setLookupResult(null);
    setDirty(true);
  };

  const meta = useMemo(() => ({
    landxml_curve_index: landxml?.curve_presets?.[landxmlPreset]?.landxml_curve_index,
    landxml_curve_id: landxml?.curve_presets?.[landxmlPreset]?.landxml_curve_id,
    project_name: inputs.project_name?.trim() || "Unnamed project",
    route_name: inputs.route_name?.trim() || "Unnamed route",
    alignment_name: inputs.alignment_name?.trim() || "Unnamed alignment",
    curve_name: inputs.curve_name?.trim() || "Unnamed curve",
    curve_direction: inputs.curve_direction || "left",
  }), [inputs, landxml, landxmlPreset]);

  const run = async (label: string, task: () => Promise<any>) => {
    setError("");
    setNotice("");
    setBusy(label);
    try {
      return await task();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      return null;
    } finally {
      setBusy("");
    }
  };

  const calculate = async () => {
    const sequence = ++calculationSequence.current;
    const result = await run("Calculating", () => call("calculate", { inputs }));
    if (result && sequence === calculationSequence.current) {
      setCalculation(result);
      setLookupResult(null);
      setDirty(true);
      const key = calculationInputKey(inputs);
      if (lastTrackedCalculation.current !== key) {
        lastTrackedCalculation.current = key;
        trackCalculatorEvent("superelevation", "calculation_completed");
      }
    } else if (!result) {
      const key = calculationInputKey(inputs);
      if (lastTrackedFailure.current !== key) {
        lastTrackedFailure.current = key;
        trackCalculatorEvent("superelevation", "calculation_failed", "runtime");
      }
    }
  };

  const calculationKey = useMemo(() => calculationInputKey(inputs), [inputs]);

  useEffect(() => {
    if (runtime !== "ready") return;
    if (!String(inputs.criteria_profile || "").startsWith("mdot") && !allows(entitlement, CAPABILITIES.allDotProfiles)) return;
    const loadedCurve = loadedCurveCalculation.current;
    if (loadedCurve?.key === calculationKey && loadedCurve.request === calculationRequest) return;
    loadedCurveCalculation.current = null;
    const readyToCalculate = String(inputs.pc ?? "").trim()
      && String(inputs.speed ?? "").trim()
      && String(inputs.radius ?? "").trim();
    const sequence = ++calculationSequence.current;
    if (!readyToCalculate) {
      setCalculation(null);
      setLookupResult(null);
      setBusy("");
      return;
    }
    const timer = window.setTimeout(async () => {
      setError("");
      setNotice("");
      setBusy("Calculating");
      try {
        const result = await call("calculate", { inputs });
        if (sequence !== calculationSequence.current) return;
        setCalculation(result);
        setLookupResult(null);
        if (lastTrackedCalculation.current !== calculationKey) {
          lastTrackedCalculation.current = calculationKey;
          trackCalculatorEvent("superelevation", "calculation_completed");
        }
      } catch (reason) {
        if (sequence === calculationSequence.current) {
          setError(reason instanceof Error ? reason.message : String(reason));
          if (lastTrackedFailure.current !== calculationKey) {
            lastTrackedFailure.current = calculationKey;
            trackCalculatorEvent("superelevation", "calculation_failed", "runtime");
          }
        }
      } finally {
        if (sequence === calculationSequence.current) setBusy("");
      }
    }, AUTO_CALC_DELAY_MS);
    return () => window.clearTimeout(timer);
    // calculationKey intentionally captures only values that affect calculation output.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calculationKey, calculationRequest, runtime, call, entitlement]);

  const diagramCurves = useMemo(() => {
    if (!curves.length) return calculation?.results ? [{ results: calculation.results, meta }] : [];
    // A saved corridor curve may include reverse-curve coordination metadata.
    // Keep that authoritative curve set on the corridor diagram until the user
    // explicitly updates it; the debounced single-curve calculation is an
    // uncoordinated preview and must not replace the saved profile after render.
    return curves;
  }, [curves, calculation?.results, meta]);

  useEffect(() => {
    if (!diagramCurves.length || runtime !== "ready") {
      setCorridorDiagram(null);
      setDiagramInspector(null);
      return;
    }
    let active = true;
    call("corridor_diagram", { curves: diagramCurves })
      .then((value) => { if (active) { setCorridorDiagram(value); setDiagramInspector(null); } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { active = false; };
  }, [diagramCurves, runtime, call]);

  useEffect(() => {
    if (!landxml || runtime !== "ready" || !allows(entitlement, CAPABILITIES.landxml)) {
      setCorridorQa(null);
      return;
    }
    let active = true;
    call("corridor_qa", { content: landxml.source.content, filename: landxml.source.filename, curves, excluded_curve_indexes: excludedCurveIndexes })
      .then((value) => { if (active) setCorridorQa(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { active = false; };
  }, [landxml, curves, excludedCurveIndexes, runtime, call, entitlement]);

  useEffect(() => {
    if (!landxml || runtime !== "ready" || !allows(entitlement, CAPABILITIES.landxml)) {
      setPlanView(null);
      return;
    }
    let active = true;
    call("plan_view", { content: landxml.source.content, filename: landxml.source.filename, curves: diagramCurves })
      .then((value) => { if (active) setPlanView(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { active = false; };
  }, [landxml, diagramCurves, runtime, call, entitlement]);

  const applyPreset = (index: number, parsed = landxml) => {
    const preset = parsed?.curve_presets?.[index];
    if (!preset) return;
    setLandxmlPreset(index);
    setInputs((current) => ({
      ...current,
      alignment_name: preset.alignment_name || "",
      curve_name: preset.curve_name || "",
      curve_direction: preset.curve_direction || "left",
      pc: preset.pc_station_label || "",
      pt: preset.pt_station_label || "",
      radius: String(preset.radius_ft ?? ""),
      station_equations: preset.station_equations || [],
      alignment_station_range: preset.alignment_station_range || null,
      route_name: current.route_name || parsed.summary?.alignment_name || "",
    }));
    setCalculation(null);
    setCalculationRequest((request) => request + 1);
    setDirty(true);
  };

  const selectLandxml = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!requestCapability(CAPABILITIES.landxml)) {
      event.target.value = "";
      return;
    }
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (landxml && !window.confirm(`Replace embedded ${landxml.source.filename} with ${file.name}? The saved project changes only when you save.`)) return;
    const content = await file.text();
    const result = await run("Reading LandXML", () => call("parse_landxml", { content, filename: file.name }));
    if (result) {
      setLandxml(result);
      setExcludedCurveIndexes([]);
      setNotice(`${file.name} is embedded in working project state. Save the project to persist it.`);
      applyPreset(0, result);
    }
  };

  const curveObject = () => calculation ? { results: calculation.results, meta, notes: inputs.curve_notes || "" } : null;

  const includeSourceCurve = (curve: Dict) => {
    const sourceIndex = curve.meta?.landxml_curve_index;
    if (sourceIndex != null) {
      setExcludedCurveIndexes((current) => current.filter((index) => index !== Number(sourceIndex)));
    }
  };

  const coordinateCurveSet = async (nextCurves: Dict[], pairs = reverseCurvePairs) => {
    if (!nextCurves.length) return nextCurves;
    return await run("Coordinating reverse curves", () => call("coordinate_reverse_curves", {
      curves: nextCurves,
      enabled: true,
      pairs,
    }));
  };

  const toggleReverseCurvePair = async (priorIndex: number) => {
    if (!requestCapability(CAPABILITIES.multiCurve)) return;
    const pair = [priorIndex, priorIndex + 1];
    const linked = reverseCurvePairs.some(([first, second]) => first === pair[0] && second === pair[1]);
    const nextPairs = linked
      ? reverseCurvePairs.filter(([first, second]) => first !== pair[0] || second !== pair[1])
      : [...reverseCurvePairs, pair].sort((left, right) => left[0] - right[0]);
    if (!linked && reverseCurvePairs.some(([first, second]) =>
      first === pair[0] || first === pair[1] || second === pair[0] || second === pair[1]
    )) {
      setError("A curve can belong to only one reverse-curve pair. Unlink the neighboring pair first.");
      return;
    }
    const coordinated = curves.length ? await coordinateCurveSet(curves, nextPairs) : curves;
    if (coordinated == null) return;
    setReverseCurvePairs(nextPairs);
    setCurves(coordinated);
    if (selectedCurve >= 0 && coordinated[selectedCurve]) {
      await loadCurveFrom(coordinated[selectedCurve], selectedCurve);
    }
    setDirty(true);
    const pairCheck = coordinated[pair[0]]?.results?.reverse_curve_coordination?.checks?.find(
      (check: Dict) => check.paired_curve_indexes?.[0] === pair[0] && check.paired_curve_indexes?.[1] === pair[1]
    );
    setNotice(linked
      ? `Unlinked Curves ${pair[0] + 1} and ${pair[1] + 1}; their independent transitions were restored.`
      : pairCheck?.status === "coordinated"
        ? `Linked Curves ${pair[0] + 1} and ${pair[1] + 1} with lane-specific standard-rate transitions.`
        : `Linked Curves ${pair[0] + 1} and ${pair[1] + 1}, but coordination is blocked. Their independent results remain unchanged; review Corridor QA.`);
  };

  const addCurve = async () => {
    if (!requestCapability(CAPABILITIES.multiCurve)) return;
    const curve = curveObject();
    if (!curve) return setError("Run a calculation before adding a curve.");
    const nextCurves = await coordinateCurveSet([...curves, curve]);
    if (!nextCurves) return;
    setCurves(nextCurves);
    includeSourceCurve(curve);
    setSelectedCurve(curves.length);
    await loadCurveFrom(nextCurves[curves.length], curves.length);
    setDirty(true);
  };

  const updateCurve = async () => {
    if (!requestCapability(CAPABILITIES.multiCurve)) return;
    const curve = curveObject();
    if (!curve || selectedCurve < 0) return setError("Select a curve and run a calculation before updating it.");
    const nextCurves = await coordinateCurveSet(curves.map((item, index) => index === selectedCurve ? curve : item));
    if (!nextCurves) return;
    setCurves(nextCurves);
    includeSourceCurve(curve);
    await loadCurveFrom(nextCurves[selectedCurve], selectedCurve);
    setDirty(true);
  };

  const removeCurve = async () => {
    if (selectedCurve < 0) return setError("Select a calculated curve before removing it.");
    const removed = curves[selectedCurve];
    const sourceIndex = removed?.meta?.landxml_curve_index;
    const remappedPairs = reverseCurvePairs
      .filter(([first, second]) => first !== selectedCurve && second !== selectedCurve)
      .map(([first, second]) => [
        first > selectedCurve ? first - 1 : first,
        second > selectedCurve ? second - 1 : second,
      ]);
    const nextCurves = await coordinateCurveSet(
      curves.filter((_, index) => index !== selectedCurve),
      remappedPairs,
    );
    if (!nextCurves) return;
    setCurves(nextCurves);
    setReverseCurvePairs(remappedPairs);
    if (sourceIndex != null) {
      setExcludedCurveIndexes((current) => [...new Set([...current, Number(sourceIndex)])].sort((a, b) => a - b));
    }
    setSelectedCurve(-1);
    setLandxmlPreset(-1);
    setCalculation(null);
    setDiagramInspector(null);
    setInputs((current) => ({
      ...current,
      alignment_name: "",
      curve_name: "",
      pc: "",
      pt: "",
      radius: "",
      station_equations: [],
      alignment_station_range: null,
      curve_notes: "",
    }));
    setDirty(true);
    setNotice(sourceIndex == null
      ? "Removed the calculated curve."
      : `Removed the calculated curve and excluded source Curve ${Number(sourceIndex) + 1} from corridor QA.`);
  };

  const loadCurveFrom = async (curve: Dict, index: number, stationFormat = inputs.station_format) => {
    setSelectedCurve(index);
    if (!curve?.results) return;
    if (curve.meta?.landxml_curve_index != null) setLandxmlPreset(Number(curve.meta.landxml_curve_index));
    const values = curve.results.inputs || {};
    setInputs((current) => {
      const nextInputs = {
        ...current,
        ...curve.meta,
        criteria_profile: values.criteria_profile ?? curve.results?.calculation_metadata?.criteria?.profile_id ?? "mdot-rdsd-2026-04-22",
        pc: values.pc ?? "", pt: values.pt ?? "", speed: String(values.speed_mph ?? ""), radius: String(values.radius_ft ?? ""),
        facility: values.facility ?? "centerline", area: values.area_type ?? "rural", lane_width: String(values.lane_width_ft ?? "12"),
        lanes_rotated: String(values.lanes_rotated ?? "2"), e_manual: values.e_manual == null ? "" : String(values.e_manual),
        friction: values.friction_input ?? "", rel_grad: values.relative_gradient_input ?? "", normal_crown: String(values.normal_crown ?? "0.02"),
        Lr_manual: values.Lr_manual == null ? "" : String(values.Lr_manual), Lt_manual: values.Lt_manual == null ? "" : String(values.Lt_manual),
        curve_notes: curve.notes || "",
      };
      loadedCurveCalculation.current = { key: calculationInputKey(nextInputs), request: calculationRequest };
      return nextInputs;
    });
    const presented = await run("Opening curve", () => call("present_results", { results: curve.results, direction: curve.meta?.curve_direction || "left", station_format: stationFormat }));
    if (presented) setCalculation(presented);
  };

  const loadCurve = async (index: number) => {
    await loadCurveFrom(curves[index], index);
  };

  const addAll = async () => {
    if (!requestCapability(CAPABILITIES.multiCurve)) return;
    if (!landxml) return setError("Select LandXML first.");
    const result = await run("Building all curves", () => call("build_all_landxml_curves", {
      content: landxml.source.content,
      filename: landxml.source.filename,
      shared_inputs: inputs,
    }));
    if (result) {
      setCurves(result);
      setReverseCurvePairs([]);
      setExcludedCurveIndexes([]);
      setSelectedCurve(result.length ? 0 : -1);
      if (result.length) await loadCurveFrom(result[0], 0);
      setDirty(true);
      setNotice(`Built ${result.length} LandXML curves for combined export.`);
    }
  };

  const exportCurves = () => curves.length ? curves : (curveObject() ? [curveObject()!] : []);

  const saveProject = async () => {
    if (!requestCapability(CAPABILITIES.projectFiles)) return;
    const filename = `${cleanName(inputs.project_name, "superelevation-project")}.json`;
    let target: SaveTarget | null;
    try {
      target = await chooseSaveTarget(filename, "application/json", "json", "Superelevation project");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      return;
    }
    if (!target) return;
    const project = {
      version: 5,
      application_version: manifest?.application_version,
      calculation_engine_version: manifest?.calculation_engine_version,
      criteria: calculation?.results?.calculation_metadata?.criteria || manifest?.criteria,
      vars: Object.fromEntries(Object.entries(inputs).filter(([key]) => key !== "coordinate_reverse_curves")),
      curves,
      excluded_landxml_curve_indexes: excludedCurveIndexes,
      reverse_curve_pairs: reverseCurvePairs,
      last_results: calculation?.results || null,
      last_meta: meta,
      landxml_source: landxml?.source || null,
    };
    const content = await run("Preparing project", () => call("project_save", { project }));
    if (content) {
      const outcome = await saveExport(target, filename, content, "application/json");
      setDirty(false);
      setNotice(`Project ${outcome} with calculation provenance and embedded LandXML.`);
    }
  };

  const loadProject = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!requestCapability(CAPABILITIES.projectFiles)) {
      event.target.value = "";
      return;
    }
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    let content: string;
    try {
      content = await file.text();
    } catch {
      setError(`Could not read ${file.name}. Select a saved JSON project file and try again.`);
      return;
    }
    if (!content.trim()) {
      setError("The selected project file is empty. Select a saved JSON project file.");
      return;
    }
    if (file.name.toLowerCase().endsWith(".xml") || content.trimStart().startsWith("<")) {
      setError("Use Select LandXML to open XML alignment files. Open accepts saved JSON project files.");
      return;
    }
    const loaded = await run("Opening project", () => call("project_load", { content }));
    if (!loaded) return;
    const restoredInputs = { ...INITIAL_INPUTS, ...(loaded.project.vars || {}) };
    const restoredCurves = loaded.project.curves || [];
    setInputs(restoredInputs);
    setCurves(restoredCurves);
    setReverseCurvePairs(loaded.project.reverse_curve_pairs || []);
    setExcludedCurveIndexes(loaded.project.excluded_landxml_curve_indexes || []);
    setLandxml(loaded.landxml || null);

    const hasLandxmlCurves = (loaded.landxml?.curve_presets?.length || 0) > 0;
    const firstLandxmlCurve = hasLandxmlCurves
      ? restoredCurves.findIndex((curve: Dict) => Number(curve.meta?.landxml_curve_index) === 0)
      : -1;

    if (firstLandxmlCurve >= 0) {
      await loadCurveFrom(restoredCurves[firstLandxmlCurve], firstLandxmlCurve, restoredInputs.station_format);
    } else if (hasLandxmlCurves) {
      applyPreset(0, loaded.landxml);
      setSelectedCurve(-1);
    } else if (loaded.project.last_results) {
      const presented = await run("Restoring results", () => call("present_results", { results: loaded.project.last_results, direction: loaded.project.last_meta?.curve_direction || "left", station_format: loaded.project.vars?.station_format !== false }));
      if (!presented) return;
      setCalculation(presented);
      setLandxmlPreset(-1);
      setSelectedCurve(-1);
    } else {
      setCalculation(null);
      setLandxmlPreset(-1);
      setSelectedCurve(-1);
    }
    setDirty(false);
    const migrationWarnings = loaded.project.migration_warnings || [];
    setNotice(
      `Opened ${file.name}${loaded.landxml ? " with embedded LandXML" : ""}.`
      + (migrationWarnings.length ? ` ${migrationWarnings.join(" ")}` : "")
    );
  };

  const loadSampleCalculation = () => {
    if (dirty && !window.confirm("Replace the current unsaved workspace with the synthetic sample calculation?")) return;
    setInputs({
      ...INITIAL_INPUTS,
      project_name: "Synthetic free sample",
      route_name: "Training example",
      alignment_name: "Manual alignment",
      curve_name: "45 mph rural curve",
      pc: "100+00",
      speed: "45",
      radius: "2000",
    });
    setCalculation(null);
    setCurves([]);
    setReverseCurvePairs([]);
    setLandxml(null);
    setLandxmlPreset(0);
    setSelectedCurve(-1);
    setExcludedCurveIndexes([]);
    setLookupResult(null);
    setError("");
    setNotice("Loaded a synthetic manual example. Review every input before use.");
    setDirty(true);
  };

  const newProject = () => {
    if (dirty && !window.confirm("Discard the unsaved working project?")) return;
    setInputs(INITIAL_INPUTS); setCalculation(null); setCurves([]); setReverseCurvePairs([]); setLandxml(null); setLandxmlPreset(0); setSelectedCurve(-1); setExcludedCurveIndexes([]);
    setLookupResult(null); setError(""); setNotice(""); setDirty(false);
  };

  const performLookup = async () => {
    if (!calculation?.results) return setError("Run a calculation first.");
    const result = await run("Looking up", () => call("lookup", {
      results: calculation.results, direction: inputs.curve_direction, station: lookupStation, slope: lookupSlope,
    }));
    if (result) setLookupResult(result);
  };

  const inspectDiagramStation = async (station: number, curveIndex: number) => {
    const curve = diagramCurves[curveIndex];
    if (!curve?.results) return;
    const value = await run("Inspecting station", () => call("diagram_lookup", {
      results: curve.results,
      direction: curve.meta?.curve_direction || "left",
      station,
    }));
    if (value) setDiagramInspector({ ...value, curve_index: curveIndex, curve_name: curve.meta?.curve_name || `Curve ${curveIndex + 1}` });
  };

  const openQaFinding = async (finding: Dict) => {
    const sourceIndex = finding.curve_indexes?.[0];
    if (sourceIndex == null) return;
    const curveIndex = curves.findIndex((curve, index) => Number(curve.meta?.landxml_curve_index ?? index) === Number(sourceIndex));
    if (curveIndex >= 0) await loadCurve(curveIndex);
  };

  const performExport = async (operation: string, extension: string, mime: string) => {
    const capability = operation === "export_pdf"
      ? CAPABILITIES.pdfReports
      : operation === "export_ord_csv"
        ? CAPABILITIES.ordCsv
        : CAPABILITIES.overlayDxf;
    if (!requestCapability(capability)) return;
    const available = exportCurves();
    if (!available.length) return setError("Run a calculation before exporting.");
    const payload: Dict = { curves: available };
    if (operation === "export_pdf" && corridorQa) payload.corridor_qa = corridorQa;
    if (operation === "export_overlay_dxf") {
      if (!landxml) return setError("Select LandXML before exporting an overlay DXF.");
      payload.landxml_source = landxml.source;
    }
    const details = EXPORT_DETAILS[operation] || { suffix: "", description: `${extension.toUpperCase()} export` };
    const filename = `${cleanName(inputs.project_name, "superelevation")}${details.suffix}.${extension}`;
    let target: SaveTarget | null;
    try {
      target = await chooseSaveTarget(filename, mime, extension, details.description);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      return;
    }
    if (!target) return;
    const outcome = await run("Generating export", async () => {
      const result = await call(operation, payload);
      const disposition = await saveExport(target, filename, result.content, mime);
      return { ...result, disposition };
    });
    if (!outcome) return;
    trackCalculatorEvent("superelevation", "export_completed", extension);
    const action = outcome.disposition === "saved" ? "Saved" : "Downloaded";
    setNotice(outcome.warnings?.length ? `${action} with ${outcome.warnings.length} warning(s): ${outcome.warnings[0]}` : `${action} ${extension.toUpperCase()} export.`);
  };

  const inputValue = (key: string) => {
    const value = inputs[key];
    if (key === "station_equations" && Array.isArray(value)) {
      return value.map((equation: Dict) => `${equation.staBack}=${equation.staAhead}`).join("; ");
    }
    if (Array.isArray(value)) return value.join(",");
    return value ?? "";
  };

  const input = (key: string, label: string, required = false, type = "text") => (
    <label className="field"><span>{label}{required && <b> *</b>}</span><input type={type} value={inputValue(key)} onChange={(e) => update(key, e.target.value)} /></label>
  );

  const result = calculation?.results;
  const lanes = calculation?.lanes || {};
  const criteria = result?.calculation_metadata?.criteria || {};
  const activeProfileId = inputs.criteria_profile || "mdot-rdsd-2026-04-22";
  const activeProfile = manifest?.criteria_profiles?.find((profile: Dict) => profile.profile_id === activeProfileId);
  const profileOptions = manifest?.options?.profiles?.[activeProfileId] || {};
  const isTdot = activeProfileId.startsWith("tdot");
  const speedOptions = isTdot && inputs.area === "urban"
    ? (profileOptions.urban_speed || profileOptions.speed || [])
    : (profileOptions.speed || manifest?.options?.speed || []);
  const applicableDrawings: string[] = criteria.applicable_standard_drawings || [];
  const criteriaSources: Dict[] = criteria.calculation_sources || [];
  const applicableLabel = applicableDrawings.length
    ? applicableDrawings.join(" / ")
    : "No mapped standard drawing";
  const qaHighlights = (corridorQa?.findings || []).filter((finding: Dict) =>
    finding.start_ft != null && finding.end_ft != null
  );
  const linkedGap = (index: number) => reverseCurvePairs.some(
    ([first, second]) => first === index && second === index + 1
  );
  const gapConflict = (index: number) => reverseCurvePairs.some(
    ([first, second]) =>
      (first === index || second === index || first === index + 1 || second === index + 1)
      && !(first === index && second === index + 1)
  );
  const reversePairCheck = (index: number) => (
    curves[index]?.results?.reverse_curve_coordination?.checks || []
  ).find((check: Dict) =>
    check.paired_curve_indexes?.[0] === index && check.paired_curve_indexes?.[1] === index + 1
  );
  const pairStatusText = (index: number) => {
    const check = reversePairCheck(index);
    if (!check) return "Link only the two curves in this pair.";
    const available = Number(check.available_tangent_ft || 0).toFixed(2);
    const minimum = Number(check.minimum_tangent_ft || 0).toFixed(2);
    if (check.status !== "coordinated") {
      return `Blocked · ${available} ft available / ${minimum} ft minimum · ${check.failure_reason || "Review Corridor QA."}`;
    }
    const left = check.lanes?.left;
    const right = check.lanes?.right;
    const laneControl = (lane: Dict | undefined) => {
      const hold = lane?.normal_crown_hold;
      if (hold) {
        return `NC hold ${Number(hold.start_ft).toFixed(3)}–${Number(hold.end_ft).toFixed(3)}`;
      }
      if (lane?.handoff_station_ft != null) {
        return `handoff ${Number(lane.handoff_station_ft).toFixed(3)} at ${Number(lane.handoff_slope_pct).toFixed(2)}%`;
      }
      return "control point unavailable";
    };
    return `Standard rate · ${available} ft available / ${minimum} ft minimum · L ${laneControl(left)} · R ${laneControl(right)}`;
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark">SE</div>
        <div><p className="eyebrow">Civil design workspace</p><h1>Superelevation Calculator</h1></div>
        <a className="workspace-home" href="/">Product home</a><a className="workspace-home" href="/account" target="_blank" rel="noreferrer">{entitlement.plan === "free" ? "Account" : `${entitlement.plan.toUpperCase()} account`}</a>
        {localDevelopment && <label className="development-entitlement"><span>Local test plan</span><select value={entitlement.plan} onChange={(event) => changeDevelopmentEntitlement(event.target.value as CommercialPlan)}><option value="free">Free</option><option value="pro">Pro</option><option value="team">Team</option></select></label>}
        <div className={`runtime ${runtime}`}><span></span>{runtime === "ready" ? "Private browser engine ready" : runtimeMessage}</div>
      </header>

      {upgradeFeature && <UpgradeNotice feature={upgradeFeature} onClose={() => setUpgradeFeature("")} />}

      {runtime !== "ready" && <section className="runtime-gate" role="status">
        <div className="gate-card"><p className="eyebrow">Browser-only processing</p><h2>{runtime === "error" ? "The workspace could not start" : runtimeMessage}</h2>
          <div className="progress"><i style={{ width: `${progress}%` }} /></div>
          <p>{runtime === "error" ? "Check your connection and retry. No project information was transmitted." : "Python and the engineering libraries are loading into this tab. Your project files never upload to a server."}</p>
          {runtime === "error" && <button className="primary" onClick={startWorker}>Retry</button>}
        </div>
      </section>}

      <div className="privacy-strip"><strong>Local processing</strong><span>LandXML, calculations, and exports remain on this device.</span><span className="version">App {manifest?.application_version || "…"} · Engine {manifest?.calculation_engine_version || "…"}</span></div>

      {(error || notice) && <div className={`toast ${error ? "error" : "notice"}`} role="alert"><strong>{error ? "Action needed" : "Complete"}</strong><span>{error || notice}</span><button aria-label="Dismiss message" onClick={() => { setError(""); setNotice(""); }}>×</button></div>}

      <div className="workspace">
        <aside className="panel project-panel">
          <div className="panel-heading"><div><p className="step">01</p><h2>Project</h2></div>{dirty && <span className="dirty">Unsaved</span>}</div>
          <div className="button-grid"><button onClick={newProject}>New</button>{allows(entitlement, CAPABILITIES.projectFiles) ? <label className="button">Open<input type="file" accept=".json,application/json" onChange={loadProject} /></label> : <button onClick={() => requestCapability(CAPABILITIES.projectFiles)}>Open {proChip(CAPABILITIES.projectFiles)}</button>}<button onClick={saveProject} disabled={runtime !== "ready"}>Save {proChip(CAPABILITIES.projectFiles)}</button></div>
          {entitlement.plan === "free" && <button className="sample-button" onClick={loadSampleCalculation}>Load synthetic sample <span>Free</span></button>}
          {input("project_name", "Project name")}{input("route_name", "Route name")}
          <div className="source-card">
            <div><p className="eyebrow">Alignment source</p><strong>{landxml?.source?.filename || "No LandXML selected"}</strong></div>
            {allows(entitlement, CAPABILITIES.landxml) ? <label className="button accent">{landxml ? "Replace XML" : "Select LandXML"}<input type="file" accept=".xml,text/xml,application/xml" onChange={selectLandxml} /></label> : <button className="button accent" onClick={() => requestCapability(CAPABILITIES.landxml)}>Select LandXML {proChip(CAPABILITIES.landxml)}</button>}
            {landxml && <><p>{landxml.summary.alignment_name || "Unnamed alignment"} · {landxml.summary.linear_unit || "units undeclared"}</p><p>CRS: {landxml.summary.coordinate_system?.display_name || "Not declared in LandXML"}</p><p>{landxml.summary.curve_count} curves · {excludedCurveIndexes.length} excluded from QA · SHA {landxml.source.sha256.slice(0, 10)}…</p><button onClick={addAll} disabled={!inputs.speed}>Add all LandXML curves</button></>}
            <p className="reverse-curve-guidance"><strong>Reverse-curve pairs {proChip(CAPABILITIES.multiCurve)}</strong> Link eligible adjacent curves below. Each curve can belong to one pair; standard rates and the 0.7Lr minimum are checked in Corridor QA.</p>
          </div>
          <div className="curve-list"><div className="list-title"><h3>Calculated curves</h3><span>{curves.length}</span></div>
            {curves.length === 0 ? <p className="empty">Add a calculated curve to build a combined export set.</p> : curves.map((curve, index) => <div className="curve-list-item" key={index}>
              <button className={selectedCurve === index ? "selected" : ""} onClick={() => loadCurve(index)}><strong>{curve.meta?.curve_name || `Curve ${index + 1}`}</strong><span>{curve.meta?.alignment_name} · {curve.meta?.curve_direction}</span></button>
              {index < curves.length - 1 && <div className={`reverse-pair-link ${linkedGap(index) ? "linked" : ""}`}>
                <button
                  onClick={() => toggleReverseCurvePair(index)}
                  disabled={!linkedGap(index) && gapConflict(index)}
                  aria-pressed={linkedGap(index)}
                >
                  {linkedGap(index) ? `Unlink Curves ${index + 1}–${index + 2}` : `Link Curves ${index + 1}–${index + 2}`}
                </button>
                <small>{gapConflict(index) && !linkedGap(index) ? "Unavailable because one curve is already paired." : pairStatusText(index)}</small>
              </div>}
            </div>)}
          </div>
          <div className="button-grid"><button onClick={addCurve}>Add {proChip(CAPABILITIES.multiCurve)}</button><button onClick={updateCurve}>Update {proChip(CAPABILITIES.multiCurve)}</button><button onClick={removeCurve}>Remove</button></div>
        </aside>

        <section className="panel inputs-panel">
          <div className="panel-heading"><div><p className="step">02</p><h2>Curve inputs</h2></div><span className="required-note">* Required</span></div>
          {(landxml?.curve_presets?.length || 0) > 0 && <label className="field full"><span>LandXML curve</span><select value={landxmlPreset} onChange={(e) => {
            const index = Number(e.target.value);
            if (index >= 0) applyPreset(index);
            else { setLandxmlPreset(-1); setCalculation(null); setDiagramInspector(null); }
          }}><option value={-1}>No LandXML curve selected</option>{landxml?.curve_presets?.map((preset: Dict, index: number) => <option value={index} key={index}>{preset.curve_name} · {preset.curve_direction} · R {preset.radius_ft}{excludedCurveIndexes.includes(index) ? " · excluded from QA" : ""}</option>)}</select></label>}
          <div className="form-grid">{input("alignment_name", "Alignment name")}{input("curve_name", "Curve name")}
            <label className="field full"><span>Governing standard</span><select value={activeProfileId} onChange={(e) => updateCriteriaProfile(e.target.value)}>{manifest?.criteria_profiles?.map((profile: Dict) => <option value={profile.profile_id} key={profile.profile_id}>{profile.governing_authority} · {profile.revision}{profile.profile_id.startsWith("tdot") && !allows(entitlement, CAPABILITIES.allDotProfiles) ? " · Pro" : ""}</option>)}</select><small>{activeProfile?.profile_name}</small></label>
            <label className="field"><span>Curve direction</span><select value={inputs.curve_direction} onChange={(e) => update("curve_direction", e.target.value)}><option value="left">Left</option><option value="right">Right</option></select></label>
            {input("pc", "PC station", true)}{input("pt", "PT station")}
            <label className="field"><span>Design speed <b>*</b></span><select value={inputs.speed} onChange={(e) => update("speed", e.target.value)}><option value="">Select mph</option>{speedOptions.map((speed: string) => <option key={speed}>{speed}</option>)}</select></label>
            {input("radius", "Curve radius (ft)", true, "number")}
            <label className="field"><span>{isTdot ? "Roadway layout" : "Facility / rotation"}</span><select value={inputs.facility} disabled={!isTdot && inputs.area === "local"} onChange={(e) => update("facility", e.target.value)}>{(profileOptions.facility || manifest?.options?.facility || []).map((value: string) => <option value={value} key={value}>{value.replace(/\b\w/g, (letter) => letter.toUpperCase())}</option>)}</select></label>
            <label className="field"><span>Area type</span><select value={inputs.area} onChange={(e) => { const area = e.target.value; setInputs((current) => ({ ...current, area, speed: isTdot && area === "urban" && Number(current.speed) > 60 ? "" : current.speed })); setDirty(true); }}>{(profileOptions.area || manifest?.options?.area || []).map((value: string) => <option value={value} key={value}>{value.replace(/\b\w/g, (letter) => letter.toUpperCase())}</option>)}</select></label>
            {input("lane_width", "Lane width (ft)", false, "number")}{input("lanes_rotated", "Lanes rotated", false, "number")}
          </div>
          <button className="advanced-toggle" aria-expanded={advancedOpen} onClick={() => setAdvancedOpen(!advancedOpen)}><span>Advanced settings</span><small>Optional criteria overrides and stationing</small><b>{advancedOpen ? "−" : "+"}</b></button>
          {advancedOpen && <div className="advanced-grid">{input("e_manual", "Manual e")}{input("friction", "Side friction")}{input("rel_grad", "Relative gradient")}{input("normal_crown", "Normal crown")}{input("Lr_manual", "Runoff Lr (ft)")}{input("Lt_manual", "Runout Lt (ft)")}{input("station_equations", "Station equations")}{input("alignment_station_range", "Internal station range")}</div>}
          <label className="field full"><span>Curve notes</span><textarea value={inputs.curve_notes} onChange={(e) => update("curve_notes", e.target.value)} rows={3} /></label>
          <div className="compute-bar"><label className="check"><input type="checkbox" checked={inputs.station_format} onChange={(e) => update("station_format", e.target.checked)} /> Station format</label><span className="auto-status">Calculates automatically</span><button onClick={() => { setInputs((current) => ({ ...INITIAL_INPUTS, project_name: current.project_name, route_name: current.route_name })); setCalculation(null); }}>Clear curve</button><button className="primary" onClick={calculate} disabled={runtime !== "ready" || !!busy}>{busy || (calculation ? "Recompute now" : "Compute now")}</button></div>
        </section>

        <section className="panel results-panel">
          <div className="panel-heading"><div><p className="step">03</p><h2>Results</h2></div>{result && <span className="criteria-tag">{criteria.governing_authority || "Criteria"} sources recorded</span>}</div>
          {!result ? <><div className="results-empty"><div className="road-crown"><i></i><i></i></div><h3>Ready for curve inputs</h3><p>Enter PC, speed, and radius to calculate transition stations and signed lane slopes.</p></div>{landxml && <SuperelevationAnalysis corridor={corridorDiagram} plan={planView} activeCurveIndex={selectedCurve} qa={corridorQa} inspector={diagramInspector} highlights={qaHighlights} onChartStation={inspectDiagramStation} onFinding={openQaFinding} />}</> : <>
            <div className="metric-grid"><article><span>Rate e</span><strong>{Number(result.e || 0).toFixed(4)}</strong><small>{result.e_source || "automatic"}</small></article><article><span>Runoff Lr</span><strong>{Number(result.Lr || 0).toFixed(2)}′</strong><small>{inputs.Lr_manual ? "override" : "automatic"}</small></article><article><span>Runout Lt</span><strong>{Number(result.Lt || 0).toFixed(2)}′</strong><small>{inputs.Lt_manual ? "override" : "automatic"}</small></article></div>
            <div className="criteria-reference">
              <p>Applicable drawing</p><strong>{applicableLabel}</strong>
              <p>Calculation sources</p>
              <ul>{criteriaSources.map((source: Dict, index: number) => <li key={`${source.component}-${source.reference}-${index}`}><span>{source.component}</span><b>{source.reference}</b>{source.mode === "user_override" && <em>User override</em>}</li>)}</ul>
            </div>
            {(result.warnings || []).length > 0 && <div className="result-warning"><strong>Engineering review</strong><ul>{result.warnings.map((warning: string, index: number) => <li key={index}>{warning}</li>)}</ul></div>}
            <SuperelevationAnalysis corridor={corridorDiagram} plan={planView} activeCurveIndex={selectedCurve} qa={corridorQa} inspector={diagramInspector} highlights={qaHighlights} onChartStation={inspectDiagramStation} onFinding={openQaFinding} />
            <div className="result-tabs"><h3>Lane events</h3><label className="check"><input type="checkbox" checked={inputs.station_format} onChange={(e) => update("station_format", e.target.checked)} /> Station labels</label></div>
            <div className="lane-tables">{(["left", "right"] as const).map((lane) => <div key={lane}><h4>{lane} lane</h4><table><thead><tr><th>Point</th><th>Station</th><th>Slope</th></tr></thead><tbody>{(lanes[lane] || []).map((row: Dict, index: number) => <tr key={index}><td>{row.label}</td><td>{row.station}</td><td className={String(row.slope_label).startsWith("+") ? "positive" : ""}>{row.slope_label}</td></tr>)}</tbody></table></div>)}</div>
            <div className="lookup"><h3>Engineering lookup</h3><div><input aria-label="Lookup station" placeholder="Station" value={lookupStation} onChange={(e) => setLookupStation(e.target.value)} /><input aria-label="Lookup superelevation" placeholder="Super (2%, 2, or 0.02)" value={lookupSlope} onChange={(e) => setLookupSlope(e.target.value)} /><button onClick={performLookup}>Lookup</button></div>{lookupResult && <div className="lookup-output">
              {lookupResult.station && <section className="lookup-card"><div className="lookup-heading"><span>Station</span><strong>{lookupResult.station.label}</strong></div><div className="lookup-lanes">{(["left", "right"] as const).map((lane) => <article key={lane}><span>{lane} lane</span><strong>{lookupResult.station.slopes[lane].label}</strong><small>{lookupResult.station.slopes[lane].decimal} ft/ft</small></article>)}</div></section>}
              {lookupResult.slope && <section className="lookup-card"><div className="lookup-heading"><span>Slope target</span><strong>{lookupResult.slope.label}</strong><small>{lookupResult.slope.decimal} ft/ft</small></div><div className="lookup-match-grid">{(["left", "right"] as const).map((lane) => <article className="lookup-matches" key={lane}><h4>{lane} lane</h4>{(lookupResult.lanes[lane] || []).length ? <ul>{lookupResult.lanes[lane].map((match: Dict, index: number) => <li key={index}><span>{match.label}</span><strong>{match.is_range ? `${match.start} – ${match.end}` : match.start}</strong>{match.nearest && <em>Nearest</em>}</li>)}</ul> : <p>No matching station</p>}</article>)}</div></section>}
            </div>}</div>
          </>}
        </section>
      </div>

      <section className="exports panel"><div><p className="step">04</p><h2>Review & export {proChip(CAPABILITIES.pdfReports)}</h2><p>Exports use the same recorded calculation results shown above. Supported browsers open a Save dialog; others use Downloads.</p></div><div className="crs-status"><span>Overlay coordinates</span><strong>{landxml?.summary?.coordinate_system?.display_name || "Select LandXML to detect"}</strong><small>DXF preserves the LandXML XY coordinates without reprojection.</small></div><div className="export-buttons"><button onClick={() => performExport("export_pdf", "pdf", "application/pdf")}>PDF report {proChip(CAPABILITIES.pdfReports)}</button><button onClick={() => performExport("export_ord_csv", "csv", "text/csv")}>ORD CSV {proChip(CAPABILITIES.ordCsv)}</button><button className="primary" onClick={() => performExport("export_overlay_dxf", "dxf", "application/dxf")}>Overlay DXF {proChip(CAPABILITIES.overlayDxf)}</button></div></section>

      <footer><p><strong>Engineering aid.</strong> The licensed professional responsible for the project must independently verify criteria, inputs, stationing, coordinate systems, results, and deliverables against governing standards and project requirements.</p><p>{entitlement.plan === "free" ? "Free without account" : `${entitlement.plan.toUpperCase()} access`} · Local files · Browser processing</p></footer>
    </main>
  );
}
