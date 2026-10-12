export const MAX_LANDXML_BYTES = 1024 * 1024;
export const MAX_ENGINEERING_BODY_BYTES = MAX_LANDXML_BYTES * 6 + 2048;

export type EngineeringSample = {
  kind: "calculation";
  standard: string;
  speed: number;
  radius: number;
  pc: string;
  pt: string;
};
export type LandxmlSample = { kind: "landxml"; retain: true; content: string };
export type EngineeringInput = EngineeringSample | LandxmlSample;

const station = /^[+-]?\d+(?:\+\d+)?(?:\.\d+)?$/;
export function parseEngineeringSample(value: unknown): EngineeringInput | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const v = value as Record<string, unknown>;
  if (v.kind === "landxml") {
    if (Object.keys(v).some(k => !["kind", "retain", "content"].includes(k))) return null;
    if (v.retain !== true || typeof v.content !== "string") return null;
    if (new TextEncoder().encode(v.content).byteLength > MAX_LANDXML_BYTES) return null;
    // Do not parse untrusted XML on the server or resolve external entities.
    if (!/<(?:[\w.-]+:)?LandXML(?:\s|>)/i.test(v.content)) return null;
    return { kind: "landxml", retain: true, content: v.content };
  }
  if (v.kind !== "calculation" || Object.keys(v).some(k => !["kind", "standard", "speed", "radius", "pc", "pt"].includes(k))) return null;
  if (typeof v.standard !== "string" || !/^[a-z0-9-]{1,96}$/.test(v.standard)) return null;
  if (typeof v.speed !== "number" || !Number.isFinite(v.speed) || v.speed <= 0 || v.speed > 1000) return null;
  if (typeof v.radius !== "number" || !Number.isFinite(v.radius) || v.radius <= 0 || v.radius > 1e9) return null;
  if (typeof v.pc !== "string" || v.pc.length > 48 || !station.test(v.pc)) return null;
  if (typeof v.pt !== "string" || v.pt.length > 48 || (v.pt !== "" && !station.test(v.pt))) return null;
  return { kind: "calculation", standard: v.standard, speed: v.speed, radius: v.radius, pc: v.pc, pt: v.pt };
}

export async function readEngineeringBody(request: Request): Promise<unknown> {
  if (Number(request.headers.get("content-length") || 0) > MAX_ENGINEERING_BODY_BYTES) throw new Error("Too large");
  if (!request.body) throw new Error("Missing body");
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_ENGINEERING_BODY_BYTES) { await reader.cancel(); throw new Error("Too large"); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder().decode(bytes));
}
