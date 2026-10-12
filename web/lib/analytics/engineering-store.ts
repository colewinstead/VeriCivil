import { env } from "cloudflare:workers";
import type { EngineeringInput, EngineeringSample } from "./engineering";

export type EngineeringReport = {
  calculations: Array<EngineeringSample & { count: number }>;
  files: Array<{ id: string; createdAt: string; bytes: number }>;
};

export async function purgeEngineeringAnalytics() {
  await env.DB.batch([
    env.DB.prepare("DELETE FROM engineering_samples WHERE created_at < datetime('now', '-90 days')"),
    env.DB.prepare("DELETE FROM retained_landxml WHERE created_at < datetime('now', '-30 days')"),
  ]);
}

export async function recordEngineeringSample(input: EngineeringInput) {
  await purgeEngineeringAnalytics();
  if (input.kind === "landxml") {
    // Bound public ingestion to 100 retained files; never store account/session/IP identifiers.
    const result = await env.DB.prepare(`INSERT INTO retained_landxml (id, content, bytes)
      SELECT ?, ?, ? WHERE (SELECT COUNT(*) FROM retained_landxml) < 100`)
      .bind(crypto.randomUUID(), input.content, new TextEncoder().encode(input.content).byteLength).run();
    return result.meta.changes > 0;
  }
  // Daily aggregate, without a per-user identifier or precise activity timestamp.
  const result = await env.DB.prepare(`INSERT INTO engineering_samples (event_day, standard, speed, radius, pc, pt, sample_count)
    SELECT date('now'), ?, ?, ?, ?, ?, 1 WHERE
      (SELECT COUNT(*) FROM engineering_samples) < 10000 OR EXISTS
      (SELECT 1 FROM engineering_samples WHERE event_day = date('now') AND standard = ? AND speed = ? AND radius = ? AND pc = ? AND pt = ?)
    ON CONFLICT(event_day, standard, speed, radius, pc, pt) DO UPDATE SET sample_count = sample_count + 1`)
    .bind(input.standard, input.speed, input.radius, input.pc, input.pt, input.standard, input.speed, input.radius, input.pc, input.pt).run();
  return result.meta.changes > 0;
}

export async function loadEngineeringAnalytics(days: number): Promise<EngineeringReport> {
  await purgeEngineeringAnalytics();
  const [calculations, files] = await Promise.all([
    env.DB.prepare(`SELECT standard, speed, radius, pc, pt, SUM(sample_count) AS count FROM engineering_samples
      WHERE event_day >= date('now', ?) GROUP BY standard, speed, radius, pc, pt ORDER BY count DESC LIMIT 200`)
      .bind(`-${Math.max(0, days - 1)} days`).all<EngineeringSample & { count: number }>(),
    env.DB.prepare(`SELECT id, created_at AS createdAt, bytes FROM retained_landxml
      WHERE created_at >= datetime('now', '-30 days') ORDER BY created_at DESC LIMIT 100`).all<{ id: string; createdAt: string; bytes: number }>(),
  ]);
  return { calculations: calculations.results.map((row: EngineeringSample & { count: number }) => ({ ...row, kind: "calculation" })), files: files.results };
}

export async function retainedLandxml(id: string) {
  await purgeEngineeringAnalytics();
  return env.DB.prepare("SELECT content FROM retained_landxml WHERE id = ? AND created_at >= datetime('now', '-30 days')")
    .bind(id).first<{ content: string }>();
}
