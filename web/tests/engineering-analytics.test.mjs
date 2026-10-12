import assert from "node:assert/strict";
import test from "node:test";
import { register } from "node:module";
import { readFile } from "node:fs/promises";
import { DatabaseSync } from "node:sqlite";
import { parseEngineeringSample, readEngineeringBody, MAX_LANDXML_BYTES, MAX_ENGINEERING_BODY_BYTES } from "../lib/analytics/engineering.ts";
import { retainLandxml, trackEngineeringCalculation } from "../lib/analytics/client.ts";

const calculation = { kind: "calculation", standard: "mdot-rdsd-2026-04-22", speed: 55, radius: 1450.5, pc: "100+25.5", pt: "110+50" };
register("./cloudflare-loader.mjs", import.meta.url);
test("retains exact engineering values without accepting identifiers or arbitrary fields", () => {
  assert.deepEqual(parseEngineeringSample(calculation), calculation);
  for (const field of ["account", "session_token", "filename", "project_name", "coordinates", "results"]) {
    assert.equal(parseEngineeringSample({ ...calculation, [field]: "private" }), null);
  }
  for (const radius of [NaN, Infinity, -1, 0, 1e10]) assert.equal(parseEngineeringSample({ ...calculation, radius }), null);
  assert.equal(parseEngineeringSample({ ...calculation, pc: "my project" }), null);
  assert.equal(parseEngineeringSample({ ...calculation, pt: "" })?.pt, "");
});

test("D1 storage aggregates exact values, bounds file capacity, and expires files/statistics", async () => {
  const { env } = await import("./cloudflare-workers-mock.mjs");
  const { recordEngineeringSample, loadEngineeringAnalytics, retainedLandxml } = await import("../lib/analytics/engineering-store.ts");
  const db = new DatabaseSync(":memory:");
  db.exec(await readFile(new URL("../drizzle/0005_strong_polaris.sql", import.meta.url), "utf8"));
  env.DB = {
    prepare(sql) {
      let args = [];
      const statement = {
        bind(...values) { args = values; return statement; },
        async run() { const result = db.prepare(sql).run(...args); return { meta: { changes: Number(result.changes) } }; },
        async all() { return { results: db.prepare(sql).all(...args) }; },
        async first() { return db.prepare(sql).get(...args) || null; },
      };
      return statement;
    },
    async batch(statements) { return Promise.all(statements.map(statement => statement.run())); },
  };
  try {
    assert.equal(await recordEngineeringSample(calculation), true);
    assert.equal(await recordEngineeringSample(calculation), true);
    const report = await loadEngineeringAnalytics(30);
    assert.equal(report.calculations.length, 1);
    assert.equal(report.calculations[0].count, 2);
    assert.equal(report.calculations[0].radius, 1450.5);
    assert.equal(report.calculations[0].pc, "100+25.5");
    const content = '<LandXML><Project name="private" /></LandXML>';
    assert.equal(await recordEngineeringSample({ kind: "landxml", retain: true, content }), true);
    const files = (await loadEngineeringAnalytics(30)).files;
    assert.equal(files.length, 1);
    assert.equal((await retainedLandxml(files[0].id)).content, content);
    assert.deepEqual(Object.keys(files[0]).sort(), ["bytes", "createdAt", "id"]);
    db.prepare("UPDATE retained_landxml SET created_at = datetime('now', '-31 days')").run();
    db.prepare("UPDATE engineering_samples SET created_at = datetime('now', '-91 days'), event_day = date('now', '-91 days')").run();
    assert.equal(await retainedLandxml(files[0].id), null);
    assert.equal((await loadEngineeringAnalytics(90)).calculations.length, 0);
    assert.equal(db.prepare("SELECT COUNT(*) AS count FROM retained_landxml").get().count, 0);
    for (let i = 0; i < 100; i++) assert.equal(await recordEngineeringSample({ kind: "landxml", retain: true, content }), true);
    assert.equal(await recordEngineeringSample({ kind: "landxml", retain: true, content }), false);
  } finally { db.close(); env.DB = null; }
});
test("LandXML collection requires explicit retention flag and bounds UTF-8 content", () => {
  const file = { kind: "landxml", retain: true, content: '<LandXML><Project name="test" /></LandXML>' };
  assert.deepEqual(parseEngineeringSample(file), file);
  assert.equal(parseEngineeringSample({ ...file, retain: false }), null);
  assert.equal(parseEngineeringSample({ kind: "landxml", content: file.content }), null);
  assert.equal(parseEngineeringSample({ ...file, content: "<html />" }), null);
  assert.equal(parseEngineeringSample({ ...file, content: `<LandXML>${"é".repeat(MAX_LANDXML_BYTES / 2)}</LandXML>` }), null);
});
test("bounded request reader rejects oversized streaming bodies without Content-Length", async () => {
  let cancelled = false;
  const request = new Request("https://example.test", { method: "POST", duplex: "half", body: new ReadableStream({
    pull(controller) { controller.enqueue(new Uint8Array(MAX_ENGINEERING_BODY_BYTES + 1)); },
    cancel() { cancelled = true; },
  }) });
  await assert.rejects(readEngineeringBody(request), /Too large/);
  assert.equal(cancelled, true);
  assert.deepEqual(await readEngineeringBody(new Request("https://example.test", { method: "POST", body: JSON.stringify(calculation) })), calculation);
});
test("opted-out imports and Do Not Track transmit no file contents; permitted uploads omit credentials", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  const requests = [];
  Object.defineProperty(globalThis, "window", { value: {}, configurable: true });
  Object.defineProperty(globalThis, "navigator", { value: { doNotTrack: "0" }, configurable: true });
  globalThis.fetch = async (url, options) => { requests.push({ url, options }); return new Response(null, { status: 202 }); };
  try {
    const content = "<LandXML />";
    assert.equal(await retainLandxml(content, false), "skipped");
    assert.equal(requests.length, 0);
    globalThis.navigator.doNotTrack = "1";
    assert.equal(await retainLandxml(content, true), "skipped");
    trackEngineeringCalculation({ criteria_profile: "mdot", speed: 55, radius: 1000, pc: "100+00" });
    assert.equal(requests.length, 0);
    globalThis.navigator.doNotTrack = "0";
    assert.equal(await retainLandxml(content, true), "stored");
    assert.equal(requests[0].options.credentials, "omit");
    assert.deepEqual(JSON.parse(requests[0].options.body), { kind: "landxml", retain: true, content });
    assert.equal(await retainLandxml("x".repeat(MAX_LANDXML_BYTES + 1), true), "unavailable");
    assert.equal(requests.length, 1);
    globalThis.fetch = async () => { throw new Error("offline"); };
    assert.equal(await retainLandxml(content, true), "unavailable");
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow); else delete globalThis.window;
    if (originalNavigator) Object.defineProperty(globalThis, "navigator", originalNavigator); else delete globalThis.navigator;
  }
});
