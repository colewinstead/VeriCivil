"use client";

import type { AnalyticsCalculator, AnalyticsEventName } from "./events";
import type { EngineeringSample } from "./engineering";

const SESSION_KEY = "vericivil_usage_session";
let memorySessionToken = "";

function sessionToken() {
  if (memorySessionToken) return memorySessionToken;
  try {
    const existing = window.sessionStorage.getItem(SESSION_KEY);
    if (existing) return (memorySessionToken = existing);
    const created = window.crypto.randomUUID();
    window.sessionStorage.setItem(SESSION_KEY, created);
    return (memorySessionToken = created);
  } catch {
    return (memorySessionToken ||= window.crypto.randomUUID());
  }
}

export function trackEngineeringCalculation(inputs: Record<string, unknown>) {
  if (typeof window === "undefined" || navigator.doNotTrack === "1") return;
  const sample: EngineeringSample = {
    kind: "calculation", standard: String(inputs.criteria_profile || ""),
    speed: Number(inputs.speed), radius: Number(inputs.radius),
    pc: String(inputs.pc ?? "").trim(), pt: String(inputs.pt ?? "").trim(),
  };
  void fetch("/api/analytics/engineering", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(sample), credentials: "omit", keepalive: true,
  }).catch(() => undefined);
}

export async function retainLandxml(content: string, allowed: boolean): Promise<"stored" | "skipped" | "unavailable"> {
  if (!allowed || typeof window === "undefined" || navigator.doNotTrack === "1") return "skipped";
  if (new TextEncoder().encode(content).byteLength > 1024 * 1024) return "unavailable";
  try {
    const response = await fetch("/api/analytics/engineering", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "landxml", retain: true, content }), credentials: "omit",
    });
    return response.status === 202 ? "stored" : "unavailable";
  } catch { return "unavailable"; }
}

export function trackCalculatorEvent(
  calculator: AnalyticsCalculator,
  event: AnalyticsEventName,
  detail = "",
) {
  if (typeof window === "undefined" || navigator.doNotTrack === "1") return;
  const body = JSON.stringify({ session_token: sessionToken(), calculator, event, detail });
  void fetch("/api/analytics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    credentials: "same-origin",
    keepalive: true,
  }).catch(() => undefined);
}
