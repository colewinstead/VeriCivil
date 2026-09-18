import entitlementPublicKey from "./entitlement-public-key.json";

export type CommercialPlan = "free" | "pro" | "team";
export type EntitlementStatus = "active" | "grace" | "unavailable";

export type CommercialManifest = {
  production_default_plan: CommercialPlan;
  browser_grace_days: number;
  desktop_grace_days: number;
  plans: Record<CommercialPlan, { name: string; capabilities: string[] }>;
  capabilities: Record<string, { name: string; description: string; minimum_plan: CommercialPlan }>;
};

export type EntitlementSnapshot = {
  plan: CommercialPlan;
  capabilities: string[];
  source: string;
  status: EntitlementStatus;
  browser_grace_days: number;
  desktop_grace_days: number;
  issued_at?: number;
  offline_expires_at?: number;
};

export interface EntitlementProvider {
  getSnapshot(): Promise<EntitlementSnapshot>;
  refresh(): Promise<EntitlementSnapshot>;
}

export const CAPABILITIES = {
  landxml: "landxml_workflows",
  multiCurve: "multi_curve_projects",
  allDotProfiles: "all_dot_profiles",
  projectFiles: "project_files",
  pdfReports: "pdf_reports",
  ordCsv: "ord_csv_export",
  overlayDxf: "overlay_dxf_export",
} as const;

export const EMPTY_FREE_ENTITLEMENT: EntitlementSnapshot = {
  plan: "free",
  capabilities: [],
  source: "production-default",
  status: "active",
  browser_grace_days: 7,
  desktop_grace_days: 30,
};

export function allows(snapshot: EntitlementSnapshot, capability: string) {
  return snapshot.capabilities.includes(capability);
}

export function isLocalEntitlementDevelopment() {
  if (typeof window === "undefined") return false;
  const hostname = window.location.hostname;
  if (["localhost", "127.0.0.1", "::1"].includes(hostname)) return true;
  if (process.env.NODE_ENV === "production") return false;
  return /^10\./.test(hostname)
    || /^192\.168\./.test(hostname)
    || /^172\.(1[6-9]|2\d|3[01])\./.test(hostname);
}

function requestedLocalState(): { plan: CommercialPlan; status: EntitlementStatus } {
  if (!isLocalEntitlementDevelopment()) return { plan: "free", status: "active" };
  const value = new URLSearchParams(window.location.search).get("entitlement")?.toLowerCase();
  if (value === undefined) return { plan: "pro", status: "active" };
  if (value === "pro" || value === "team") return { plan: value, status: "active" };
  if (value === "grace") return { plan: "pro", status: "grace" };
  if (value === "unavailable") return { plan: "free", status: "unavailable" };
  return { plan: "free", status: "active" };
}

export function localSnapshot(
  manifest: CommercialManifest,
  plan: CommercialPlan,
  status: EntitlementStatus = "active",
): EntitlementSnapshot {
  const effectivePlan = status === "unavailable" ? "free" : plan;
  return {
    plan: effectivePlan,
    capabilities: [...manifest.plans[effectivePlan].capabilities],
    source: "local-development",
    status,
    browser_grace_days: manifest.browser_grace_days,
    desktop_grace_days: manifest.desktop_grace_days,
  };
}

export class LocalDevelopmentEntitlementProvider implements EntitlementProvider {
  constructor(
    private readonly manifest: CommercialManifest,
    private plan: CommercialPlan = requestedLocalState().plan,
    private status: EntitlementStatus = requestedLocalState().status,
  ) {}

  setState(plan: CommercialPlan, status: EntitlementStatus = "active") {
    this.plan = plan;
    this.status = status;
  }

  async getSnapshot() {
    return localSnapshot(this.manifest, this.plan, this.status);
  }

  async refresh() {
    return this.getSnapshot();
  }
}

const ENTITLEMENT_CACHE_KEY = "superelevation.entitlement.v1";

function decodeBase64Url(value: string) {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function verifiedTokenSnapshot(token: string) {
  const [version, payload, signature, extra] = token.split(".");
  if (version !== "v1" || !payload || !signature || extra) return null;
  try {
    const key = await crypto.subtle.importKey(
      "jwk",
      entitlementPublicKey as JsonWebKey,
      { name: "Ed25519" },
      false,
      ["verify"],
    );
    const valid = await crypto.subtle.verify(
      "Ed25519",
      key,
      decodeBase64Url(signature),
      new TextEncoder().encode(`v1.${payload}`),
    );
    if (!valid) return null;
    return normalizedRemoteSnapshot(JSON.parse(new TextDecoder().decode(decodeBase64Url(payload))));
  } catch (error) {
    console.warn("Entitlement token verification failed.", error);
    return null;
  }
}

function normalizedRemoteSnapshot(value: unknown): EntitlementSnapshot | null {
  if (!value || typeof value !== "object") return null;
  const snapshot = value as Partial<EntitlementSnapshot>;
  if (!(["free", "pro", "team"] as string[]).includes(String(snapshot.plan))) return null;
  if (!(["active", "grace", "unavailable"] as string[]).includes(String(snapshot.status))) return null;
  if (!Array.isArray(snapshot.capabilities) || !snapshot.capabilities.every((item) => typeof item === "string")) return null;
  return snapshot as EntitlementSnapshot;
}

export class RemoteEntitlementProvider implements EntitlementProvider {
  constructor(private readonly manifest: CommercialManifest) {}

  async getSnapshot() {
    return this.refresh();
  }

  async refresh() {
    try {
      const response = await fetch("/api/entitlement", { cache: "no-store" });
      if (!response.ok) throw new Error("Entitlement service unavailable.");
      const payload = await response.json() as { entitlement?: unknown; entitlement_token?: string };
      const unsignedSnapshot = normalizedRemoteSnapshot(payload.entitlement);
      const snapshot = payload.entitlement_token
        ? await verifiedTokenSnapshot(payload.entitlement_token)
        : unsignedSnapshot?.plan === "free"
          ? {
              ...localSnapshot(this.manifest, "free", unsignedSnapshot.status),
              source: unsignedSnapshot.source,
            }
          : null;
      if (!snapshot) throw new Error("Invalid entitlement response.");
      if (payload.entitlement_token) localStorage.setItem(ENTITLEMENT_CACHE_KEY, payload.entitlement_token);
      return snapshot;
    } catch (error) {
      console.warn("Entitlement refresh failed; checking offline grace.", error);
      return this.cachedFallback();
    }
  }

  private async cachedFallback() {
    const now = Math.floor(Date.now() / 1000);
    try {
      const snapshot = await verifiedTokenSnapshot(localStorage.getItem(ENTITLEMENT_CACHE_KEY) || "");
      if (snapshot && snapshot.plan !== "free" && Number(snapshot.offline_expires_at || 0) >= now) {
        return { ...snapshot, source: "cached-offline-grace", status: "grace" as const };
      }
    } catch {
      // Invalid or user-edited cache fails closed to Free.
    }
    return localSnapshot(this.manifest, "free", "unavailable");
  }
}
