import assert from "node:assert/strict";
import test from "node:test";
import { crossSectionPreview, previewStationLabel } from "../lib/cross-section-preview.ts";

const frames = [0, 100].map(station => ({ station_ft: station, segments: [{
  name: "Lane 1", side: "left", width_ft: 12, slope_pct: -2 + station / 10,
  left: { x: 12, y: -0.24 + station * 0.012 }, right: { x: 0, y: 0 },
}] }));

test("preview geometry and signed percentages use the same continuous station fraction", () => {
  for (const station of [0, 12.345, 25, 50, 99.9, 100]) {
    const [segment] = crossSectionPreview(frames, station);
    assert.ok(Math.abs(segment.slope_pct - (-2 + station / 10)) < 1e-12);
    assert.ok(Math.abs(segment.left.y - segment.slope_pct * 0.12) < 1e-12);
    assert.equal(segment.right.y, 0);
    assert.equal(segment.width_ft, 12);
    assert.match(segment.slope_label, /^≈ [+-]?\d+\.\d{2}%$/);
  }
  assert.equal(crossSectionPreview(frames, 0)[0].slope_label, "≈ -2.00%");
  assert.equal(crossSectionPreview(frames, 25)[0].slope_label, "≈ +0.50%");
  assert.equal(crossSectionPreview(frames, 20)[0].slope_label, "≈ 0.00%");
});

test("preview respects each breakpoint and refuses unavailable or mismatched geometry", () => {
  const middle = { station_ft: 50, segments: [{ ...frames[0].segments[0], slope_pct: -6, left: { x: 12, y: -0.72 } }] };
  assert.equal(crossSectionPreview([frames[0], middle, frames[1]], 50)[0].slope_pct, -6);
  assert.equal(crossSectionPreview([frames[0], middle, frames[1]], 25)[0].slope_pct, -4);
  for (const station of [-1, 101]) assert.equal(crossSectionPreview(frames, station), null);
  assert.equal(crossSectionPreview([], 0), null);
  assert.equal(crossSectionPreview([{ station_ft: 0, segments: [] }], 0), null);
  assert.equal(crossSectionPreview([frames[0], { ...frames[1], segments: [{ ...frames[1].segments[0], name: "Other curve" }] }], 50), null);
});

test("station previews retain station format and apply Python-provided equation spans", () => {
  const ordinary = [0, 2000].map(station => ({station_ft: station, civil_station_ft: station, station: `${station / 100}+00.000`, station_suffix: ""}));
  assert.equal(previewStationLabel(ordinary, 1012.852), "10+12.852");
  assert.equal(previewStationLabel(ordinary, 0), "0+00.000");
  for (const ahead of [2500, 1000]) {
    const equation = [{station_ft: 1000, civil_station_ft: 1000, station: "10+00.000", station_suffix: "R1"},
      {station_ft: 1500, civil_station_ft: ahead, station: `${ahead / 100}+00.000R2`, station_suffix: "R2"},
      {station_ft: 2000, civil_station_ft: ahead + 500, station: `${(ahead + 500) / 100}+00.000R2`, station_suffix: "R2"}];
    assert.equal(previewStationLabel(equation, 1499.999), "14+99.999R1");
    assert.equal(previewStationLabel(equation, 1500), `${ahead / 100}+00.000R2`);
    assert.equal(previewStationLabel(equation, 1500.001), `${ahead / 100}+00.001R2`);
    assert.equal(previewStationLabel(equation, 1600), `${(ahead + 100) / 100}+00.000R2`);
  }
  assert.equal(previewStationLabel([], 1000), "");
  assert.equal(previewStationLabel(ordinary, -1), "");
  assert.equal(previewStationLabel(ordinary, 2001), "");
});
