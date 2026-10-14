import assert from "node:assert/strict";
import test from "node:test";
import { groupQaFindings, requiresCompoundCalculation } from "../lib/qa-findings.ts";

test("pending curves stay separate while calculation blocks lead the actionable findings", () => {
  const pending = { code: "UNCALCULATED_CURVE", severity: "block" };
  const review = { code: "GEOMETRY_REVIEW", severity: "review" };
  const block = { code: "INSUFFICIENT_TANGENT", severity: "block" };
  const source = [pending, review, block];
  assert.deepEqual(groupQaFindings(source, "all"), { actionable: [block, review], pending: [pending] });
  assert.deepEqual(groupQaFindings(source, "block"), { actionable: [block], pending: [pending] });
  assert.deepEqual(groupQaFindings(source, "review"), { actionable: [review], pending: [] });
  assert.deepEqual(source, [pending, review, block]);
  assert.deepEqual(groupQaFindings([pending], "all"), { actionable: [], pending: [pending] });
});

test("unbuilt compound curves wait for their included neighbors", () => {
  assert.equal(requiresCompoundCalculation([3], [], false), true);
  assert.equal(requiresCompoundCalculation([3], [3], false), false);
  assert.equal(requiresCompoundCalculation([3], [], true), false);
  assert.equal(requiresCompoundCalculation(undefined, [], false), false);
});
