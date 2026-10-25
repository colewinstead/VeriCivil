import { getProductUser } from "@/app/product-auth";
import { isProductAdmin } from "@/lib/auth/admin";
import { requireSameOrigin } from "@/lib/billing/request-security";
import { parseEngineeringSample, readEngineeringBody } from "@/lib/analytics/engineering";
import { recordEngineeringSample } from "@/lib/analytics/engineering-store";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try { requireSameOrigin(request); } catch (error) { if (error instanceof Response) return error; throw error; }
  if (request.headers.get("dnt") === "1") return new Response(null, { status: 204 });
  let input;
  try { input = parseEngineeringSample(await readEngineeringBody(request)); } catch { input = null; }
  if (!input) return Response.json({ error: "Invalid engineering sample." }, { status: 400 });
  try {
    const user = await getProductUser();
    if (user && isProductAdmin(user)) return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    const stored = await recordEngineeringSample(input);
    return new Response(null, { status: stored ? 202 : 429, headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ error: "Analytics unavailable." }, { status: 503 }); }
}
