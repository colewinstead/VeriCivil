const PYODIDE_VERSION = "0.29.4";
const desktop = self.location.protocol === "vericivil:";
const PYODIDE_BASE = desktop ? "/pyodide/" : `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
let runtimePromise;
let activeCalculator;

function status(message, progress) {
  self.postMessage({ type: "status", message, progress });
}

async function initialize(calculator = "superelevation") {
  if (activeCalculator && activeCalculator !== calculator) {
    throw new Error("This browser workspace is already assigned to another calculator.");
  }
  if (runtimePromise) return runtimePromise;
  activeCalculator = calculator;
  runtimePromise = (async () => {
    status(desktop ? "Loading local desktop workspace…" : "Loading private browser workspace…", 12);
    importScripts(`${PYODIDE_BASE}pyodide.js`);
    const pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });
    const runtimeManifest = await (await fetch("/python/manifest.json", { cache: "no-cache" })).json();
    const bundle = runtimeManifest.calculators?.[calculator];
    if (!bundle) throw new Error(`Unknown calculator runtime: ${calculator}.`);

    if (bundle.pyodide_packages.length) {
      status("Loading engineering dependencies…", 36);
      await pyodide.loadPackage(bundle.pyodide_packages);
    }
    if (bundle.micropip_packages.length) {
      pyodide.globals.set("_micropip_packages_json", JSON.stringify(bundle.micropip_packages));
      pyodide.globals.set("_offline_bundle", !!bundle.offline);
      await pyodide.runPythonAsync(`
import json
import micropip
await micropip.install(json.loads(_micropip_packages_json), deps=not _offline_bundle)
`);
      pyodide.globals.delete("_micropip_packages_json");
      pyodide.globals.delete("_offline_bundle");
    }

    status("Loading shared calculation engine…", 70);
    pyodide.FS.mkdirTree("/app");
    for (const moduleName of bundle.modules) {
      const response = await fetch(`/python/${moduleName}`, { cache: "no-cache" });
      if (!response.ok) throw new Error(`Could not load ${moduleName}.`);
      const slash = moduleName.lastIndexOf("/");
      if (slash >= 0) pyodide.FS.mkdirTree(`/app/${moduleName.slice(0, slash)}`);
      pyodide.FS.writeFile(`/app/${moduleName}`, await response.text(), { encoding: "utf8" });
    }
    pyodide.runPython(`
import sys
sys.path.insert(0, "/app")
import vericivil_service
`);
    pyodide.globals.set("_web_calculator", calculator);
    const manifestProxy = pyodide.runPython("vericivil_service.application_manifest(_web_calculator)");
    const appManifest = manifestProxy.toJs({ dict_converter: Object.fromEntries });
    manifestProxy.destroy();
    status(desktop ? "Local desktop engine ready" : "Ready — files never leave this browser", 100);
    self.postMessage({ type: "ready", manifest: appManifest });
    return pyodide;
  })();
  return runtimePromise;
}

function convertResult(result) {
  if (result && typeof result.toJs === "function") {
    const converted = result.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
    result.destroy();
    return converted;
  }
  return result;
}

self.onmessage = async (event) => {
  const { id, calculator = "superelevation", operation, payload = {} } = event.data || {};
  if (operation === "initialize") {
    try {
      await initialize(calculator);
    } catch (error) {
      runtimePromise = undefined;
      activeCalculator = undefined;
      self.postMessage({ type: "fatal", message: error?.message || String(error) });
    }
    return;
  }
  try {
    const pyodide = await initialize(calculator);
    const payloadJson = JSON.stringify(payload);
    pyodide.globals.set("_web_calculator", calculator);
    pyodide.globals.set("_web_operation", operation);
    pyodide.globals.set("_web_payload", payloadJson);
    const proxy = pyodide.runPython(
      "vericivil_service.dispatch_safe(_web_calculator, _web_operation, _web_payload)",
    );
    const response = convertResult(proxy);
    self.postMessage({ type: "response", id, ...response });
  } catch (error) {
    self.postMessage({
      type: "response",
      id,
      ok: false,
      error: { message: error?.message || String(error), details: error?.stack || "" },
    });
  }
};
