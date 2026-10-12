import { env } from "cloudflare:workers";
import type { AnalyticsCalculator, AnalyticsEventInput } from "./events";
import { loadEngineeringAnalytics, type EngineeringReport } from "./engineering-store";

export type AnalyticsTotals = {
  openedSessions: number;
  calculatingSessions: number;
  calculations: number;
  errors: number;
  exports: number;
};

export type AnalyticsReport = {
  available: boolean;
  days: number;
  generatedAt: string;
  summary: AnalyticsTotals;
  calculators: Array<AnalyticsTotals & { calculator: AnalyticsCalculator }>;
  daily: Array<AnalyticsTotals & { day: string }>;
  engineering: EngineeringReport;
};

export function emptyUsageAnalytics(days = 30): AnalyticsReport {
  return {
    available: false,
    days,
    generatedAt: new Date().toISOString(),
    summary: { openedSessions: 0, calculatingSessions: 0, calculations: 0, errors: 0, exports: 0 },
    calculators: [],
    daily: [],
    engineering: { calculations: [], files: [] },
  };
}

type AggregateRow = {
  calculator_id?: string;
  event_day?: string;
  opened_sessions: number | string | null;
  calculating_sessions: number | string | null;
  calculations: number | string | null;
  errors: number | string | null;
  exports: number | string | null;
};

function analyticsDb() {
  if (!env.DB) throw new Error("Usage analytics storage is unavailable.");
  return env.DB;
}

async function dailySessionHash(eventDay: string, sessionToken: string) {
  const bytes = new TextEncoder().encode(`${eventDay}:${sessionToken}`);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function totals(row?: AggregateRow): AnalyticsTotals {
  return {
    openedSessions: Number(row?.opened_sessions || 0),
    calculatingSessions: Number(row?.calculating_sessions || 0),
    calculations: Number(row?.calculations || 0),
    errors: Number(row?.errors || 0),
    exports: Number(row?.exports || 0),
  };
}

const AGGREGATES = `
  COUNT(DISTINCT CASE WHEN event_name = 'calculator_opened' THEN session_hash END) AS opened_sessions,
  COUNT(DISTINCT CASE WHEN event_name = 'calculation_completed' THEN session_hash END) AS calculating_sessions,
  COALESCE(SUM(CASE WHEN event_name = 'calculation_completed' THEN event_count ELSE 0 END), 0) AS calculations,
  COALESCE(SUM(CASE WHEN event_name = 'calculation_failed' THEN event_count ELSE 0 END), 0) AS errors,
  COALESCE(SUM(CASE WHEN event_name = 'export_completed' THEN event_count ELSE 0 END), 0) AS exports
`;

export async function recordUsageEvent(input: AnalyticsEventInput) {
  const db = analyticsDb();
  const eventDay = new Date().toISOString().slice(0, 10);
  const sessionHash = await dailySessionHash(eventDay, input.sessionToken);
  await db.batch([
    db.prepare("DELETE FROM analytics_events WHERE event_day < date('now', '-90 days')"),
    db.prepare(`
      INSERT INTO analytics_events (
        event_day, session_hash, calculator_id, event_name, event_detail, event_count, first_seen_at, last_seen_at
      ) VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
      ON CONFLICT (event_day, session_hash, calculator_id, event_name, event_detail)
      DO UPDATE SET event_count = analytics_events.event_count + 1, last_seen_at = CURRENT_TIMESTAMP
    `).bind(eventDay, sessionHash, input.calculator, input.event, input.detail),
  ]);
}

export async function loadUsageAnalytics(days = 30): Promise<AnalyticsReport> {
  const boundedDays = Math.max(1, Math.min(90, Math.trunc(days)));
  const start = new Date();
  start.setUTCDate(start.getUTCDate() - boundedDays + 1);
  const startDay = start.toISOString().slice(0, 10);
  const db = analyticsDb();
  const [summaryResult, calculatorResult, dailyResult] = await Promise.all([
    db.prepare(`SELECT ${AGGREGATES} FROM analytics_events WHERE event_day >= ?`).bind(startDay).all<AggregateRow>(),
    db.prepare(`SELECT calculator_id, ${AGGREGATES} FROM analytics_events WHERE event_day >= ? GROUP BY calculator_id ORDER BY calculations DESC`).bind(startDay).all<AggregateRow>(),
    db.prepare(`SELECT event_day, ${AGGREGATES} FROM analytics_events WHERE event_day >= ? GROUP BY event_day ORDER BY event_day DESC`).bind(startDay).all<AggregateRow>(),
  ]);
  return {
    available: true,
    days: boundedDays,
    generatedAt: new Date().toISOString(),
    summary: totals(summaryResult.results[0]),
    calculators: calculatorResult.results.map((row: AggregateRow) => ({ calculator: row.calculator_id as AnalyticsCalculator, ...totals(row) })),
    daily: dailyResult.results.map((row: AggregateRow) => ({ day: row.event_day || "", ...totals(row) })),
    engineering: await loadEngineeringAnalytics(boundedDays),
  };
}
