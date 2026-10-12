import { getProductUser } from "@/app/product-auth";
import { isProductAdmin } from "@/lib/auth/admin";
import { retainedLandxml } from "@/lib/analytics/engineering-store";
import { requireSameOrigin } from "@/lib/billing/request-security";
import { env } from "cloudflare:workers";

export const dynamic = "force-dynamic";
export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const user = await getProductUser();
    if (!user || !isProductAdmin(user)) return Response.json({ error: "Not authorized." }, { status: 403 });
    const { id } = await context.params;
    if (!/^[0-9a-f-]{36}$/.test(id)) return new Response(null, { status: 404 });
    const file = await retainedLandxml(id);
    if (!file) return new Response(null, { status: 404 });
    return new Response(file.content, { headers: {
      "Content-Type": "application/octet-stream", "Content-Disposition": `attachment; filename="landxml-${id}.xml"`,
      "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    } });
  } catch { return Response.json({ error: "File unavailable." }, { status: 503 }); }
}

export async function DELETE(request: Request, context: { params: Promise<{ id: string }> }) {
  try {
    requireSameOrigin(request);
    const user = await getProductUser();
    if (!user || !isProductAdmin(user)) return Response.json({ error: "Not authorized." }, { status: 403 });
    const { id } = await context.params;
    if (!/^[0-9a-f-]{36}$/.test(id)) return new Response(null, { status: 404 });
    await env.DB.prepare("DELETE FROM retained_landxml WHERE id = ?").bind(id).run();
    return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof Response) return error;
    return Response.json({ error: "File could not be deleted." }, { status: 503 });
  }
}
