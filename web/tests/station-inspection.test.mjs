import assert from "node:assert/strict";
import test from "node:test";
import { createStationInspection } from "../lib/station-inspection.ts";

test("scrubbing keeps one in-flight lookup, coalesces waiting stations, and rejects stale results", async () => {
  const calls = [], updates = [], errors = [];
  const queue = createStationInspection(request => new Promise((resolve, reject) => calls.push({ request, resolve, reject })), value => updates.push(value), error => errors.push(error), () => {});
  queue.request({ station: 100, curveIndex: 0 });
  queue.request({ station: 101, curveIndex: 0 });
  queue.request({ station: 102, curveIndex: 1 });
  assert.equal(calls.length, 1);
  calls[0].resolve("obsolete");
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(updates, []);
  assert.deepEqual(calls[1].request, { station: 102, curveIndex: 1 });
  calls[1].resolve("current");
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(updates, ["current"]);
  queue.request({ station: 103, curveIndex: 1 });
  queue.cancel();
  calls[2].reject(new Error("obsolete dataset"));
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(!errors.includes("obsolete dataset"));
  assert.deepEqual(updates, ["current"]);
});

test("invalid station errors are shown and a new selection recovers", async () => {
  const errors = [], updates = [], busy = [];
  const queue = createStationInspection(async ({ station }) => {
    if (typeof station === "string") throw new Error("Ambiguous station; use an internal reference.");
    return station;
  }, value => updates.push(value), error => errors.push(error), value => busy.push(value));
  queue.request({ station: "10+00", curveIndex: 0 });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(errors.at(-1), /Ambiguous station/);
  queue.request({ station: 1000, curveIndex: 0 });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(updates, [1000]);
  assert.equal(errors.at(-1), "");
  assert.equal(busy.at(-1), false);
});
