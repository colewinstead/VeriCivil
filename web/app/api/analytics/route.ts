import { getProductUser } from "@/app/product-auth";
import { isProductAdmin } from "@/lib/auth/admin";
import { requireSameOrigin } from "@/lib/billing/request-security";
import { parseAnalyticsEvent } from "@/lib/analytics/events";
import { recordUsageEvent } from "@/lib/analytics/store";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    requireSameOrigin(request);
    if (request.headers.get("dnt") === "1") return new Response(null, { status: 204 });
    const length = Number(request.headers.get("content-length") || 0);
    if (length > 1024) return Response.json({ error: "Invalid analytics event." }, { status: 400 });
    const event = parseAnalyticsEvent(await request.json());
    if (!event) return Response.json({ error: "Invalid analytics event." }, { status: 400 });
    const user = await getProductUser();
    if (user && isProductAdmin(user)) return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    await recordUsageEvent(event);
    return new Response(null, { status: 202, headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof Response) return error;
    return Response.json({ error: "Usage event was not recorded." }, { status: 503 });
  }
}
