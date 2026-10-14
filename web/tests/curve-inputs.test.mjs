import assert from "node:assert/strict";
import test from "node:test";
import { editLandxmlInputs, curveInputValues } from "../lib/curve-inputs.ts";

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
