import assert from "node:assert/strict";
import test from "node:test";
import { registerHooks } from "node:module";
import { parseAnalyticsEvent } from "../lib/analytics/events.ts";

const base = {
  session_token: "018f47a2-9b2d-7cc1-8db1-6e9f8f81b218",
  calculator: "superelevation",
};

test("analytics accepts only bounded product events", () => {
  assert.deepEqual(parseAnalyticsEvent({ ...base, event: "calculation_completed", detail: "" }), {
    sessionToken: base.session_token,
    calculator: "superelevation",
    event: "calculation_completed",
    detail: "",
  });
  assert.equal(parseAnalyticsEvent({ ...base, event: "export_completed", detail: "pdf" })?.detail, "pdf");
  assert.equal(parseAnalyticsEvent({ ...base, calculator: "crushed_stone_base", event: "calculator_opened", detail: "" })?.calculator, "crushed_stone_base");
});

test("analytics rejects engineering inputs and unbounded details", () => {
  assert.equal(parseAnalyticsEvent({ ...base, event: "calculation_completed", detail: "55 mph" }), null);
  assert.equal(parseAnalyticsEvent({ ...base, event: "calculation_completed", detail: "", radius: 1450 }), null);
  assert.equal(parseAnalyticsEvent({ ...base, event: "export_completed", detail: "project-name.pdf" }), null);
  assert.equal(parseAnalyticsEvent({ ...base, event: "unknown", detail: "" }), null);
  assert.equal(parseAnalyticsEvent({ ...base, session_token: "not-a-session", event: "calculator_opened", detail: "" }), null);
});

test("analytics routes exclude authenticated admins before any storage without linking customer identity", async () => {
  const authModule = `data:text/javascript,${encodeURIComponent('export const auth = { user: null, error: null }; export async function withAuth() { if (auth.error) throw auth.error; return { user: auth.user }; }')}`;
  const hooks = registerHooks({
    resolve(specifier, context, nextResolve) {
      if (specifier === "@workos-inc/authkit-nextjs") return { url: authModule, shortCircuit: true };
      if (specifier === "cloudflare:workers") return nextResolve(new URL("./cloudflare-workers-mock.mjs", import.meta.url).href, context);
      if (specifier.startsWith("@/")) return nextResolve(new URL(`../${specifier.slice(2)}.ts`, import.meta.url).href, context);
      if (specifier.startsWith(".") && !/\.[a-z]+$/.test(specifier)) return nextResolve(`${specifier}.ts`, context);
      return nextResolve(specifier, context);
    },
  });
  const { env } = await import("./cloudflare-workers-mock.mjs");
  const originalEnv = { ...env };
  const { auth } = await import(authModule);
  const writes = [];
  Object.assign(env, {
    ADMIN_WORKOS_USER_IDS: " user_owner, user_other_admin ",
    WORKOS_API_KEY: "test", WORKOS_CLIENT_ID: "test", WORKOS_COOKIE_PASSWORD: "test", NEXT_PUBLIC_WORKOS_REDIRECT_URI: "https://example.test/auth/callback",
    DB: {
      prepare(sql) {
        let args = [];
        const statement = {
          bind(...values) { args = values; return statement; },
          async run() { writes.push({ sql, args }); return { meta: { changes: 1 } }; },
        };
        return statement;
      },
      async batch(statements) { return Promise.all(statements.map(statement => statement.run())); },
    },
  });
  try {
    const { POST: usage } = await import("../app/api/analytics/route.ts");
    const { POST: engineering } = await import("../app/api/analytics/engineering/route.ts");
    const endpoints = [
      { post: usage, path: "/api/analytics", body: { ...base, event: "calculation_completed", detail: "" } },
      { post: engineering, path: "/api/analytics/engineering", body: { kind: "calculation", standard: "mdot", speed: 55, radius: 1000, pc: "100+00", pt: "" } },
      { post: engineering, path: "/api/analytics/engineering", body: { kind: "landxml", retain: true, content: "<LandXML />" } },
    ];
    const user = { id: "user_owner", email: "owner@example.test", firstName: "Owner", lastName: null };
    for (const { post, path, body } of endpoints) {
      const request = (overrides = {}, payload = body) => new Request(`https://example.test${path}`, {
        method: "POST", headers: { origin: "https://example.test", "Content-Type": "application/json", ...overrides }, body: JSON.stringify(payload),
      });
      for (const id of ["user_owner", "user_other_admin"]) {
        auth.user = { ...user, id };
        writes.length = 0;
        const skipped = await post(request());
        assert.equal(skipped.status, 204);
        assert.equal(skipped.headers.get("cache-control"), "no-store");
        assert.equal(writes.length, 0);
      }
      // Same email is deliberately insufficient: exclusions follow the verified subject.
      for (const visitor of [null, { ...user, id: "user_customer" }]) {
        auth.user = visitor;
        writes.length = 0;
        assert.equal((await post(request())).status, 202);
        assert.ok(writes.length > 0);
        assert.doesNotMatch(JSON.stringify(writes), /user_customer|owner@example/);
      }
      for (const [headers, payload, status] of [
        [{ origin: "https://other.test" }, body, 403],
        [{ dnt: "1" }, body, 204],
        [{}, { invalid: true }, 400],
      ]) {
        writes.length = 0;
        assert.equal((await post(request(headers, payload))).status, status);
        assert.equal(writes.length, 0);
      }
      auth.error = new Error("Session verification unavailable");
      writes.length = 0;
      assert.equal((await post(request())).status, 503);
      assert.equal(writes.length, 0);
      auth.error = null;
    }
  } finally {
    for (const key of Object.keys(env)) delete env[key];
    Object.assign(env, originalEnv);
    hooks.deregister();
  }
});
