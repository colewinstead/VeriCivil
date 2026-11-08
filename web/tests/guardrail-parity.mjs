import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { loadPyodide } from "pyodide";

const root = new URL("../public/python/", import.meta.url);
const manifest = JSON.parse(await readFile(new URL("manifest.json", root), "utf8"));
const bundle = manifest.calculators.guardrail;
const pyodide = await loadPyodide();
await pyodide.loadPackage(bundle.pyodide_packages);
pyodide.globals.set("packages_json", JSON.stringify(bundle.micropip_packages));
await pyodide.runPythonAsync(`
import json, micropip
await micropip.install(json.loads(packages_json))
`);
pyodide.FS.mkdirTree("/app");
for (const name of [...bundle.modules, ...bundle.assets]) {
  pyodide.FS.mkdirTree(`/app/${name.slice(0, name.lastIndexOf("/"))}`);
  pyodide.FS.writeFile(`/app/${name}`, await readFile(new URL(name, root)));
}
const fixture = "calculators/guardrail/upstream/test_fixtures/phase3_baseline.json";
pyodide.FS.mkdirTree(`/app/${fixture.slice(0, fixture.lastIndexOf("/"))}`);
pyodide.FS.writeFile(`/app/${fixture}`, await readFile(new URL(`../../${fixture}`, import.meta.url)));
pyodide.FS.writeFile("/app/test_guardrail_browser.py", await readFile(new URL("../../test_guardrail_browser.py", import.meta.url)));
const passed = pyodide.runPython(`
import sys, unittest
sys.path.insert(0, "/app")
import test_guardrail_browser
unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_guardrail_browser)).wasSuccessful()
`);
assert.equal(passed, true, "Guardrail boundary, baseline, projects, report styles and appendices must pass in Pyodide");
console.log("Guardrail Pyodide parity passed, including 2,592 baseline cases and PDF appendices for both facilities.");
