import assert from "node:assert/strict";
import test from "node:test";
import { crossSectionPreview } from "../lib/cross-section-preview.ts";

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
