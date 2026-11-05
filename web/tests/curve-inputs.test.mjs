import assert from "node:assert/strict";
import test from "node:test";
import { editLandxmlInputs, curveInputValues, mergeCurveInputs } from "../lib/curve-inputs.ts";

test("a blocked curve's draft edits stay isolated and survive JSON save/restore", () => {
  const original = { shared: { speed: "35", runoff_tangent_percent: "50" },
    curves: { 4: { speed: "40" }, 6: { speed: "30" } } };
  const edited = editLandxmlInputs(original, { runoff_tangent_percent: "40" }, 4, "curve", [2, 3, 4, 5, 6]);
  assert.deepEqual(edited.shared, original.shared);
  assert.deepEqual(edited.curves[4], { speed: "40", runoff_tangent_percent: "40" });
  assert.deepEqual(edited.curves[6], { speed: "30" });
  assert.deepEqual(original.curves[4], { speed: "40" });
  assert.deepEqual(JSON.parse(JSON.stringify(edited)), edited);
});

test("common edits update only the changed fields on selected curves", () => {
  const state = { shared: { speed: "35" }, curves: { 4: { speed: "40" }, 0: { runoff_tangent_percent: "70" } } };
  const edited = editLandxmlInputs(state, { runoff_tangent_percent: "45" }, 4, "selected", [2, 3, 4]);
  assert.deepEqual(edited.curves[4], { speed: "40", runoff_tangent_percent: "45" });
  assert.deepEqual(edited.curves[0], state.curves[0]);
  assert.equal(edited.shared.speed, "35");
  assert.equal(edited.shared.runoff_tangent_percent, "45");
});

test("recorded curve inputs restore the editable speed and overrides", () => {
  const inputs = curveInputValues({ results: { inputs: { speed_mph: 40, radius_ft: 1800, Lr_manual: null,
    runoff_tangent_percent: "40", circular_placement_basis: "runoff_runout" } }, meta: { curve_name: "Curve 5" } });
  assert.equal(inputs.speed, "40");
  assert.equal(inputs.Lr_manual, "");
  assert.equal(inputs.runoff_tangent_percent, "40");
  assert.equal(inputs.curve_name, "Curve 5");
});

test("Case II edits preserve the other carriageway and each curve's other inputs", () => {
  const state = { shared: { case_ii: { left: { speed: "65", radius: "3000" }, right: { speed: "60", radius: "2000" } } },
    curves: { 0: { case_ii: { left: { radius: "4000" }, right: { radius: "5000" } } }, 1: { case_ii: { right: { radius: "6000" } } } } };
  const patch = { case_ii: { left: { speed: "70" } } };
  const edited = editLandxmlInputs(state, patch, 0, "selected", [0]);
  assert.deepEqual(edited.curves[0].case_ii, { left: { speed: "70", radius: "4000" }, right: { speed: "60", radius: "5000" } });
  assert.deepEqual(edited.curves[1], state.curves[1]);
  assert.equal(state.shared.case_ii.left.speed, "65");
  assert.equal(mergeCurveInputs(state.shared, patch).case_ii.right.radius, "2000");
  const restored = curveInputValues({ results: { inputs: { roadway: "divided_case_ii", radius: 500, area: "urban_freeway", case_ii: edited.curves[0].case_ii } }, meta: {} });
  assert.deepEqual(restored.case_ii, edited.curves[0].case_ii);
  assert.equal(restored.radius, "500");
  assert.equal(restored.area, "urban_freeway");
});

test("shared-corridor modes survive selected edits and legacy curves keep explicit radii", () => {
  const shared = { roadway: "divided_case_ii", case_ii_geometry_mode: "shared_corridor",
    case_ii_placement_mode: "coordinated", radius: "4000", case_ii: {left: {pivot_offset: "24"}, right: {pivot_offset: "48"}} };
  const state = editLandxmlInputs({shared, curves: {}}, {case_ii: {right: {speed: "65"}}}, 0, "curve", [0]);
  assert.equal(mergeCurveInputs(state.shared, state.curves[0]).case_ii_geometry_mode, "shared_corridor");
  const restored = curveInputValues({results: {inputs: shared}, meta: {}});
  assert.equal(restored.case_ii_placement_mode, "coordinated");
  assert.equal(restored.case_ii.right.pivot_offset, "48");
  const legacy = curveInputValues({results: {inputs: {roadway: "divided_case_ii", case_ii: shared.case_ii}}, meta: {}});
  assert.equal(legacy.case_ii_geometry_mode, "explicit_radii");
  assert.equal(legacy.case_ii_placement_mode, "independent");
  const derived = curveInputValues({results: {inputs: {...shared, case_ii_placement_mode: undefined}}, meta: {}});
  assert.equal(derived.case_ii_placement_mode, "coordinated");
});
