import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { loadPyodide } from "pyodide";

const runtimeRoot = new URL("../public/python/", import.meta.url);
const pyodide = await loadPyodide();
await pyodide.loadPackage(["micropip", "pyproj", "numpy", "fonttools", "Pillow"]);
await pyodide.runPythonAsync(`
import micropip
await micropip.install(["reportlab==4.4.7", "ezdxf==1.4.4"])
`);

pyodide.FS.mkdirTree("/app");
const manifest = JSON.parse(await readFile(new URL("manifest.json", runtimeRoot), "utf8"));
const allModules = [...new Set(Object.values(manifest.calculators).flatMap((bundle) => bundle.modules))];
for (const moduleName of allModules) {
  const slash = moduleName.lastIndexOf("/");
  if (slash >= 0) pyodide.FS.mkdirTree(`/app/${moduleName.slice(0, slash)}`);
  pyodide.FS.writeFile(`/app/${moduleName}`, await readFile(new URL(moduleName, runtimeRoot), "utf8"), { encoding: "utf8" });
}

await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/app")
import super_service
`);

const freeEntitlement = { plan: "free", status: "active" };
const proEntitlement = { plan: "pro", status: "active" };

const aashtoInputs = {
  criteria_profile: "aashto-green-book-2018-2019-10", pc: "1000", pt: "2000",
  speed: "60", radius: "1500", area: "rural", e_manual: "0.06",
  lane_widths: "12,12", normal_crown: "0.02", runoff_tangent_percent: "70", curve_direction: "left",
};
const native = (operation, input) => JSON.parse(execFileSync("python3", ["-c",
  "import json,sys,super_service; print(json.dumps(super_service.dispatch(sys.argv[1],sys.stdin.read())))", operation],
{ cwd: new URL("../../", import.meta.url), input: JSON.stringify(input), encoding: "utf8" }));
const browser = (operation, input) => {
  pyodide.globals.set("aashto_payload", JSON.stringify(input));
  pyodide.globals.set("aashto_operation", operation);
  return JSON.parse(pyodide.runPython("__import__('json').dumps(super_service.dispatch(aashto_operation,aashto_payload))"));
};
// Run the public synthetic boundary/selection cases in the browser engine too.
pyodide.FS.writeFile("/app/test_aashto_criteria.py", await readFile(new URL("../../test_aashto_criteria.py", import.meta.url), "utf8"), { encoding: "utf8" });
pyodide.runPython(`
import unittest
from test_aashto_criteria import TableSelectionTests
selection_checks = unittest.TestResult()
unittest.defaultTestLoader.loadTestsFromTestCase(TableSelectionTests).run(selection_checks)
assert selection_checks.wasSuccessful(), repr(selection_checks.errors + selection_checks.failures)
assert selection_checks.testsRun > 0
`);
console.log("Synthetic AASHTO automatic table-selection checks passed in Pyodide.");

// Licensed grids stay local; compare real automatic results when the workbook is available.
let localWorkbook;
try {
  localWorkbook = await readFile(new URL("../../docs/AASHTO Super Tables.xlsx", import.meta.url));
} catch (error) {
  if (error.code !== "ENOENT") throw error;
  console.log("Licensed AASHTO workbook absent: private table parity skipped; synthetic selection cases passed.");
}
if (localWorkbook) {
  const payload = { content_base64: localWorkbook.toString("base64") };
  const pack = browser("import_aashto_workbook", payload);
  assert.deepEqual(pack, native("import_aashto_workbook", payload));
  for (const maximum of [4, 6, 8, 10, 12]) {
    const request = { entitlement: proEntitlement, inputs: {
      ...aashtoInputs, aashto_tables: pack, e_manual: "", speed: 40, radius: 1824.076,
      max_superelevation: maximum, area: maximum === 4 ? "urban_freeway" : "rural",
    } };
    const result = browser("calculate", request);
    assert.deepEqual(result, native("calculate", request), `Automatic AASHTO ${maximum}% parity`);
    if (maximum === 8) assert.equal(result.results.e, 0.04);
  }
  console.log("Local AASHTO workbook import and automatic rates passed native/Pyodide parity for all five maxima.");
}
const aashtoCases = [
  ...[4, 6, 8, 10, 12].map(maximum => ({ max_superelevation: maximum, e_manual: String(maximum/100), area: maximum===4 ? "urban_freeway" : "rural" })),
  ...[0, 25, 50, 100].map(percent => ({ runoff_tangent_percent: percent })),
  ...["left", "right"].flatMap(direction => ["centerline", "left_edge", "right_edge"].map(pivot => ({ curve_direction: direction, rotation_axis: pivot }))),
  ...["on_tangent", "in_spiral"].map(placement => ({ alignment_type: "spiral", ts: "700", st: "2250", runout_placement: placement, acknowledge_spiral_override: true })),
  ...["-0.02", "0.02"].map(slope => ({ roadway: "one_way", initial_section: "single_slope", lane_widths: "12", rotation_axis: "left_edge", initial_slope: slope })),
];
for (const changes of aashtoCases) {
  const request = { entitlement: proEntitlement, inputs: { ...aashtoInputs, ...changes } };
  assert.deepEqual(browser("calculate", request), native("calculate", request), `AASHTO native/Pyodide parity: ${JSON.stringify(changes)}`);
}
const ramp = browser("calculate", { entitlement: proEntitlement, inputs: { ...aashtoInputs, roadway: "one_way", initial_section: "single_slope", lane_widths: "12", rotation_axis: "left_edge" } });
const rampCurve = { results: ramp.results, meta: { curve_direction: "left" } };
const rampExport = { entitlement: proEntitlement, curves: [rampCurve] };
assert.deepEqual(browser("export_ord_csv", rampExport), native("export_ord_csv", rampExport));
assert.deepEqual(Object.keys(browser("lookup", { results: ramp.results, direction: "left", station: "1000" }).station.slopes), ["Lane 1"]);
const syntheticXml = execFileSync("python3", ["-c", "from test_aashto_criteria import synthetic_alignment; print(synthetic_alignment(200,300,'right')[0],end='')"], { cwd: new URL("../../", import.meta.url), encoding: "utf8" });
assert.deepEqual(browser("parse_landxml", { entitlement: proEntitlement, content: syntheticXml, filename: "synthetic.xml" }), native("parse_landxml", { entitlement: proEntitlement, content: syntheticXml, filename: "synthetic.xml" }));
pyodide.globals.set("synthetic_spiral_xml", syntheticXml);
const coordinates = pyodide.runPython("[super_service.super_landxml.parse_landxml_text(synthetic_spiral_xml).xy_at_station(s) for s in (700,1100,1400)]");
const xy = coordinates.toJs({ create_proxies: false }); coordinates.destroy();
const expectedXy = JSON.parse(execFileSync("python3", ["-c", "import json,super_landxml,sys; d=super_landxml.parse_landxml_text(sys.stdin.read()); print(json.dumps([d.xy_at_station(s) for s in (700,1100,1400)]))"], { cwd: new URL("../../", import.meta.url), input: syntheticXml, encoding: "utf8" }));
xy.forEach((point,i) => point.forEach((value,j) => assert.ok(Math.abs(value-expectedXy[i][j])<1e-7)));

const payload = JSON.stringify({
  entitlement: freeEntitlement,
  inputs: {
    pc: "10+00", pt: "12+00", speed: "45", radius: "1000",
    facility: "centerline", area: "rural", lane_width: "12",
    lanes_rotated: "2", normal_crown: "0.02", curve_direction: "right",
  },
});
pyodide.globals.set("payload", payload);
const calculationProxy = pyodide.runPython(`super_service.dispatch("calculate", payload)`);
const calculation = calculationProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
calculationProxy.destroy();

pyodide.globals.set("pro_calculation_payload", JSON.stringify({
  entitlement: proEntitlement,
  inputs: JSON.parse(payload).inputs,
}));
const proCalculationProxy = pyodide.runPython(`super_service.dispatch("calculate", pro_calculation_payload)`);
const proCalculation = proCalculationProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
proCalculationProxy.destroy();
assert.deepEqual(proCalculation, calculation, "Entitlement tier must not alter an authorized calculation");

assert.deepEqual(
  {
    e: calculation.results.e,
    Lr: calculation.results.Lr,
    Lt: calculation.results.Lt,
    reverse_crown_ft: calculation.results.reverse_crown_ft,
    full_super_ft: calculation.results.full_super_ft,
  },
  { e: 0.08, Lr: 178, Lt: 44, reverse_crown_ft: 875.4, full_super_ft: 1053.4 },
);
assert.ok(calculation.lanes.left.length > 0);
assert.ok(calculation.lanes.right.length > 0);

pyodide.globals.set("pc_pt_regression_payload", JSON.stringify({
  entitlement: freeEntitlement,
  inputs: {
    pc: "20+08.438", pt: "30+07.098", speed: "25", radius: "1250",
    facility: "centerline", area: "rural", lane_width: "12", lanes_rotated: "2",
    normal_crown: "0.02", e_manual: "0.026", curve_direction: "right",
  },
}));
const pcPtRegressionProxy = pyodide.runPython(`super_service.dispatch("calculate", pc_pt_regression_payload)`);
const pcPtRegression = pcPtRegressionProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
pcPtRegressionProxy.destroy();
for (const [lane, expected] of [[pcPtRegression.lanes.left, 1.82], [pcPtRegression.lanes.right, -2]]) {
  assert.ok(Math.abs(lane.find((row) => row.label === "PC").slope_pct - expected) < 1e-9);
  assert.ok(Math.abs(lane.find((row) => row.label === "PT").slope_pct - expected) < 1e-9);
}
const insideEntryNc = pcPtRegression.lanes.right.find((row) => row.event_type === "Normal crown");
const insidePc = pcPtRegression.lanes.right.find((row) => row.label === "PC");
const insideRotation = pcPtRegression.lanes.right.find((row) => row.label === "BEGIN ROTATION");
assert.ok(insideEntryNc.station_ft < insidePc.station_ft);
assert.ok(insideRotation.station_ft > insidePc.station_ft);

pyodide.globals.set("diagram_payload", JSON.stringify({ results: calculation.results, direction: "right" }));
const diagramProxy = pyodide.runPython(`super_service.dispatch("curve_diagram", diagram_payload)`);
const diagram = diagramProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
diagramProxy.destroy();
assert.ok(diagram.profiles.left.length > 0);
assert.ok(diagram.markers.some((marker) => marker.kind === "PC"));

pyodide.globals.set("corridor_diagram_payload", JSON.stringify({
  curves: [
    { results: calculation.results, meta: { curve_name: "Curve A", curve_direction: "right" } },
    { results: calculation.results, meta: { curve_name: "Curve B", curve_direction: "left" } },
  ],
}));
const corridorDiagramProxy = pyodide.runPython(`super_service.dispatch("corridor_diagram", corridor_diagram_payload)`);
const corridorDiagram = corridorDiagramProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
corridorDiagramProxy.destroy();
assert.equal(corridorDiagram.curve_count, 2);
assert.deepEqual(corridorDiagram.curves.map((curve) => curve.curve_name), ["Curve A", "Curve B"]);

const reverseCurvePayload = {
  entitlement: proEntitlement,
  enabled: true,
  pairs: [[0, 1]],
  curves: [
    { results: structuredClone(calculation.results), meta: { curve_name: "Curve A", curve_direction: "right" } },
    { results: structuredClone(calculation.results), meta: { curve_name: "Curve B", curve_direction: "left" } },
  ],
};
reverseCurvePayload.curves[0].results.pt_ft = 1200;
reverseCurvePayload.curves[1].results.pc_ft = 1500;
reverseCurvePayload.curves[1].results.full_super_ft = 1553.4;
pyodide.globals.set("reverse_curve_payload", JSON.stringify(reverseCurvePayload));
const reverseCurveProxy = pyodide.runPython(`super_service.dispatch("coordinate_reverse_curves", reverse_curve_payload)`);
const reverseCurves = reverseCurveProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
reverseCurveProxy.destroy();
assert.equal(reverseCurves[0].results.full_super_out_ft, calculation.results.full_super_out_ft);
assert.equal(reverseCurves[1].results.full_super_ft, 1553.4);
assert.equal(reverseCurves[0].results.reverse_curve_coordination.checks[0].status, "coordinated");
assert.equal(reverseCurves[0].results.reverse_curve_coordination.checks[0].transition_rate_status, "standard");
assert.ok(["normal_crown_hold", "standard_rate_intersection"].includes(
  reverseCurves[0].results.reverse_curve_coordination.checks[0].lanes.left.mode,
));

pyodide.globals.set("free_reverse_curve_payload", JSON.stringify({ ...reverseCurvePayload, entitlement: freeEntitlement }));
const freeReverseCurveProxy = pyodide.runPython(`super_service.dispatch_safe("coordinate_reverse_curves", free_reverse_curve_payload)`);
const freeReverseCurve = freeReverseCurveProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
freeReverseCurveProxy.destroy();
assert.equal(freeReverseCurve.ok, false);
assert.equal(freeReverseCurve.error.type, "EntitlementRequiredError");

const tdotPayload = JSON.stringify({
  entitlement: proEntitlement,
  inputs: {
    criteria_profile: "tdot-rd11-2026-04-30",
    pc: "10+00", pt: "20+00", speed: "50", radius: "2280",
    facility: "undivided", area: "rural", lane_width: "12",
    lanes_rotated: "2", normal_crown: "0.02", curve_direction: "left",
  },
});
pyodide.globals.set("free_tdot_payload", JSON.stringify({
  ...JSON.parse(tdotPayload),
  entitlement: freeEntitlement,
}));
const freeTdotProxy = pyodide.runPython(`super_service.dispatch_safe("calculate", free_tdot_payload)`);
const freeTdot = freeTdotProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
freeTdotProxy.destroy();
assert.equal(freeTdot.ok, false);
assert.equal(freeTdot.error.type, "EntitlementRequiredError");

pyodide.globals.set("tdot_payload", tdotPayload);
const tdotProxy = pyodide.runPython(`super_service.dispatch("calculate", tdot_payload)`);
const tdot = tdotProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
tdotProxy.destroy();
assert.equal(tdot.results.calculation_metadata.criteria.profile_id, "tdot-rd11-2026-04-30");
assert.deepEqual(
  { e: tdot.results.e, Lr: tdot.results.Lr },
  { e: 0.046, Lr: 110 },
);
assert.ok(tdot.lanes.left.length > 0);
assert.ok(tdot.lanes.right.length > 0);

const landxmlPayload = JSON.stringify({
  entitlement: proEntitlement,
  filename: "tdot-coordinate-test.xml",
  content: `<?xml version="1.0"?>
<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" version="1.2">
  <Units><Imperial linearUnit="USSurveyFoot" /></Units>
  <CoordinateSystem horizontalDatum="NAD83(2011)" horizontalCoordinateSystemName="TN83/2011F" />
  <Alignments><Alignment name="TDOT Test" length="100" staStart="0"><CoordGeom>
    <Line length="100"><Start>500000 1200000 0</Start><End>500100 1200000 0</End></Line>
  </CoordGeom></Alignment></Alignments>
</LandXML>`,
});
pyodide.globals.set("landxml_payload", landxmlPayload);
const landxmlProxy = pyodide.runPython(`super_service.dispatch("parse_landxml", landxml_payload)`);
const landxml = landxmlProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
landxmlProxy.destroy();
assert.equal(landxml.summary.coordinate_system.status, "recognized");
assert.equal(landxml.summary.coordinate_system.code, "6576");
assert.equal(landxml.summary.coordinate_system.preserve_xy, true);

const corridorContent = `<?xml version="1.0"?>
<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" version="1.2">
  <Units><Imperial linearUnit="USSurveyFoot" /></Units>
  <Alignments><Alignment name="QA Test" length="2785.398" staStart="0"><CoordGeom>
    <Line length="1000"><Start>0 0 0</Start><End>0 1000 0</End></Line>
    <Curve rot="ccw" radius="500" length="785.398"><Start>0 1000 0</Start><Center>-500 1000 0</Center><End>-500 1500 0</End></Curve>
    <Line length="1000"><Start>-500 1500 0</Start><End>-500 2500 0</End></Line>
  </CoordGeom></Alignment></Alignments>
</LandXML>`;
const batchPayload = JSON.stringify({
  entitlement: proEntitlement,
  content: corridorContent,
  filename: "qa-test.xml",
  shared_inputs: { speed: "30", facility: "centerline", area: "rural", lane_width: "12", lanes_rotated: "2", normal_crown: "0.02" },
});
pyodide.globals.set("batch_payload", batchPayload);
const batchProxy = pyodide.runPython(`super_service.dispatch("build_all_landxml_curves", batch_payload)`);
const batchCurves = batchProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
batchProxy.destroy();
pyodide.globals.set("qa_payload", JSON.stringify({ entitlement: proEntitlement, content: corridorContent, filename: "qa-test.xml", curves: batchCurves }));
const qaProxy = pyodide.runPython(`super_service.dispatch("corridor_qa", qa_payload)`);
const qa = qaProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
qaProxy.destroy();
assert.equal(qa.status, "pass");
assert.equal(qa.curve_count, 1);

const cwContent = await readFile(new URL("../../tests/fixtures/cw_reverse_curve.xml", import.meta.url), "utf8");
pyodide.globals.set("cw_payload", JSON.stringify({
  entitlement: proEntitlement,
  content: cwContent,
  filename: "cw_reverse_curve.xml",
  shared_inputs: {
    speed: "65", facility: "centerline", area: "rural", lane_width: "12",
    lanes_rotated: "2", normal_crown: "0.02",
  },
}));
const cwProxy = pyodide.runPython(`super_service.dispatch("build_all_landxml_curves", cw_payload)`);
const cwCurves = cwProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
cwProxy.destroy();
assert.equal(cwCurves.length, 2);
pyodide.globals.set("cw_coordinate_payload", JSON.stringify({
  entitlement: proEntitlement,
  enabled: true,
  pairs: [[0, 1]],
  curves: cwCurves,
}));
const cwCoordinateProxy = pyodide.runPython(`super_service.dispatch("coordinate_reverse_curves", cw_coordinate_payload)`);
const coordinatedCwCurves = cwCoordinateProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
cwCoordinateProxy.destroy();
const cwCheck = coordinatedCwCurves[0].results.reverse_curve_coordination.checks[0];
assert.equal(cwCheck.status, "coordinated");
assert.ok(Math.abs(cwCheck.available_tangent_ft - 123) < 1e-6);
assert.ok(Math.abs(cwCheck.minimum_tangent_ft - 86.1) < 1e-6);
assert.equal(cwCheck.transition_rate_status, "standard");
assert.equal(cwCheck.lanes.left.mode, "normal_crown_hold");
assert.equal(cwCheck.lanes.right.mode, "normal_crown_hold");
assert.ok(cwCheck.lanes.left.normal_crown_hold.length_ft > 0);
assert.ok(cwCheck.lanes.right.normal_crown_hold.length_ft > 0);

pyodide.globals.set("plan_payload", JSON.stringify({ entitlement: proEntitlement, content: corridorContent, filename: "qa-test.xml", curves: batchCurves }));
const planProxy = pyodide.runPython(`super_service.dispatch("plan_view", plan_payload)`);
const plan = planProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
planProxy.destroy();
assert.ok(plan.entities.some((entity) => entity.type === "LINE"));
assert.ok(plan.entities.some((entity) => entity.type === "TEXT"));
assert.ok(
  plan.entities.some((entity) => entity.type === "TEXT" && entity.text_style === "Engineering Regular"),
  "Plan View should preserve the exported Engineering Regular text style",
);
assert.equal(plan.layers.ALI_DESIGN_ML_CURVES.color, 8);
assert.equal(plan.background, "#101010");
assert.equal(plan.curve_paths, undefined);

pyodide.globals.set("invalid_project_payload", JSON.stringify({ entitlement: proEntitlement, content: "" }));
const invalidProjectProxy = pyodide.runPython(`super_service.dispatch_safe("project_load", invalid_project_payload)`);
const invalidProject = invalidProjectProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
invalidProjectProxy.destroy();
assert.equal(invalidProject.ok, false);
assert.match(invalidProject.error.message, /not valid JSON/);
assert.doesNotMatch(invalidProject.error.message, /Traceback/);

pyodide.globals.set("excluded_qa_payload", JSON.stringify({
  entitlement: proEntitlement,
  content: corridorContent,
  filename: "qa-test.xml",
  curves: [],
  excluded_curve_indexes: [0],
}));
const excludedQaProxy = pyodide.runPython(`super_service.dispatch("corridor_qa", excluded_qa_payload)`);
const excludedQa = excludedQaProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
excludedQaProxy.destroy();
assert.equal(excludedQa.status, "pass");
assert.equal(excludedQa.curve_count, 0);
assert.equal(excludedQa.excluded_count, 1);

pyodide.globals.set("results_payload", JSON.stringify({
  entitlement: proEntitlement,
  curves: [{ results: calculation.results, meta: { curve_direction: "right" }, notes: "" }],
}));
const csvProxy = pyodide.runPython(`super_service.dispatch("export_ord_csv", results_payload)`);
const csv = csvProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
csvProxy.destroy();
assert.match(csv.content, /SuperelevationLane,Station,CrossSlope/);

const pdfProxy = pyodide.runPython(`super_service.dispatch("export_pdf", results_payload)`);
const pdf = pdfProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
pdfProxy.destroy();
assert.equal(String.fromCharCode(...pdf.content.slice(0, 4)), "%PDF");

const dxfProxy = pyodide.runPython(`super_service.dispatch("export_detail_dxf", results_payload)`);
const dxf = dxfProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
dxfProxy.destroy();
assert.match(new TextDecoder().decode(dxf.content), /SECTION/);

assert.deepEqual(manifest.calculators.crushed_stone_base.pyodide_packages, []);
assert.deepEqual(manifest.calculators.crushed_stone_base.micropip_packages, []);
const stonePyodide = await loadPyodide();
stonePyodide.FS.mkdirTree("/app");
for (const moduleName of manifest.calculators.crushed_stone_base.modules) {
  const slash = moduleName.lastIndexOf("/");
  if (slash >= 0) stonePyodide.FS.mkdirTree(`/app/${moduleName.slice(0, slash)}`);
  stonePyodide.FS.writeFile(`/app/${moduleName}`, await readFile(new URL(moduleName, runtimeRoot), "utf8"), { encoding: "utf8" });
}
await stonePyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/app")
import vericivil_service
`);
stonePyodide.globals.set("stone_payload", JSON.stringify({
  segments: [{ name: "Mainline", length_ft: 100, pavement_width_ft: 20, shoulder_width_ft: 5, shoulder_slope_percent: 0, side_slope_h_to_v: 4, thickness_in: 6 }],
  tons_per_cubic_yard: 1.6875,
  waste_percent: 0,
}));
const stoneProxy = stonePyodide.runPython(
  `vericivil_service.dispatch_safe("crushed_stone_base", "calculate", stone_payload)`,
);
const stone = stoneProxy.toJs({ dict_converter: Object.fromEntries, create_proxies: false });
stoneProxy.destroy();
assert.equal(stone.ok, true);
assert.equal(stone.result.segments[0].equivalent_width_per_side_ft, 1);
assert.equal(stone.result.segments[0].equivalent_width_both_sides_ft, 2);
assert.equal(stone.result.totals.cubic_feet, 1600);
assert.equal(stone.result.totals.base_tons, 100);

console.log("Pyodide superelevation and crushed stone base parity passed.");
