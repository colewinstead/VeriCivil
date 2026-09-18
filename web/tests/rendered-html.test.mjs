import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { register } from "node:module";
import test from "node:test";

register("./cloudflare-loader.mjs", import.meta.url);

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request(`http://localhost${path}`, { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("renders the VeriCivil calculator hub without starting a calculation runtime", async () => {
  const response = await render("/");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /VeriCivil \| Roadway Calculation Toolkit/i);
  assert.match(html, /Roadway calculations/i);
  assert.match(html, /you can verify/i);
  assert.match(html, /Crushed Stone Base/i);
  assert.match(html, /Superelevation Calculator/i);
  assert.match(html, /Manage Superelevation Pro/i);
  assert.match(html, /licensed professional responsible for the project/i);
  assert.doesNotMatch(html, /<form/i);
  assert.match(html, /http:\/\/localhost\/og\.png/i);
  await access(new URL("../public/og.png", import.meta.url));
  assert.match(html, /Live browser workspace/i);
  assert.match(html, /Lane profiles/i);
  assert.match(html, /Overlay DXF/i);
  assert.match(html, /PDF report/i);
  await Promise.all([
    access(new URL("../public/showcase/calculator-ui.png", import.meta.url)),
    access(new URL("../public/showcase/lane-profile-diagram.png", import.meta.url)),
    access(new URL("../public/showcase/dxf-plan-view.png", import.meta.url)),
    access(new URL("../public/showcase/pdf-report.png", import.meta.url)),
    access(new URL("../public/showcase/stone-base-results.png", import.meta.url)),
  ]);
  assert.doesNotMatch(html, /https:\/\/github\.com\/colewinstead\/VeriCivil/i);
  assert.doesNotMatch(html, /Available Tool 01|Available Tool 02|Superelevated roadway calculation illustration|Example calculator results/i);
  assert.doesNotMatch(html, /Starting private browser workspace/i);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/i);
});

test("renders the calculator directory and crushed stone base workspace", async () => {
  const [directoryResponse, stoneResponse] = await Promise.all([
    render("/calculators"),
    render("/calculators/crushed-stone-base"),
  ]);
  assert.equal(directoryResponse.status, 200);
  assert.equal(stoneResponse.status, 200);
  const [directory, stone] = await Promise.all([directoryResponse.text(), stoneResponse.text()]);
  assert.match(directory, /Focused tools for/i);
  assert.match(directory, /Superelevation Calculator/i);
  assert.match(directory, /Crushed Stone Base/i);
  assert.match(stone, /Crushed Stone Base Tonnage Calculator \| VeriCivil/i);
  assert.match(stone, /Roadway segments/i);
  assert.match(stone, /1\.6875/i);
  assert.match(stone, /Confirm before ordering/i);
  assert.match(stone, /Add segment/i);
  assert.match(stone, /US customary/i);
  const source = await readFile(new URL("../app/CrushedStoneBaseCalculator.tsx", import.meta.url), "utf8");
  assert.match(source, /AUTO_CALC_DELAY_MS = 350/);
  assert.match(source, /calculator: "crushed_stone_base"/);
  assert.match(source, /aria-invalid/);
  assert.match(source, /aria-live="polite"/);
  assert.match(source, /Pavement width \(EOP to EOP\)/i);
  assert.match(source, /Shoulder width \(each side\)/i);
  assert.match(source, /Equivalent keyout width/i);
  assert.match(source, /total for both sides/i);
  assert.match(source, /Keyout run per side/i);
  assert.match(source, /Pavement width \+ 2 × shoulder width \+ 2 × equivalent keyout width/i);
  assert.doesNotMatch(source, /localStorage|showSaveFilePicker|truckload|metric toggle/i);
});

test("renders superelevation at its permanent route and preserves compatibility query parameters", async () => {
  const response = await render("/calculators/superelevation");
  assert.equal(response.status, 200);
  const html = await response.text();
  const source = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  const upgradeSource = await readFile(new URL("../app/UpgradeNotice.tsx", import.meta.url), "utf8");
  assert.match(html, /<title>Superelevation Calculator \| VeriCivil<\/title>/i);
  assert.match(html, /CalculatorApp-[^"']+\.js/i);
  assert.match(source, /Private browser engine/i);
  assert.match(source, /Select LandXML/i);
  assert.match(source, /Curve inputs/i);
  assert.match(source, /Review & export/i);
  assert.match(source, /Load synthetic sample/i);
  assert.match(source, /entitlement\.plan === "free".*Load synthetic sample/i);
  assert.match(source, /Reverse-curve pairs/i);
  assert.match(source, /Link eligible adjacent curves below/i);
  assert.match(source, /0\.7Lr minimum/i);
  assert.match(source, /A curve can belong to only one reverse-curve pair/i);
  assert.match(source, /reverse_curve_pairs: reverseCurvePairs/i);
  assert.match(source, /Local test plan/i);
  assert.match(await readFile(new URL("../app/entitlements.ts", import.meta.url), "utf8"), /process\.env\.NODE_ENV === "production"/);
  assert.match(source, /setLocalDevelopment\(isLocalEntitlementDevelopment\(\)\)/);
  assert.match(source, /const proChip = \(capability: string\) => allows\(entitlement, capability\)/);
  assert.match(source, /PRO\} access|TOUPPERCASE\(\).*access/i);
  assert.match(source, /requestCapability/i);
  assert.match(upgradeSource, /role="dialog"/i);
  assert.match(upgradeSource, /aria-modal="true"/i);
  assert.match(upgradeSource, /Your current inputs, results, and project state are unchanged/i);
  assert.match(upgradeSource, /Keep calculating/i);
  assert.match(upgradeSource, /target="_blank"/i);
  assert.match(source, /preserves the LandXML XY coordinates without reprojection/i);
  assert.doesNotMatch(source, /Destination CRS|targetCrs|coordinate_config/i);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/i);
  const compatibilityResponse = await render("/calculator?entitlement=pro&sample=1");
  assert.ok([307, 308].includes(compatibilityResponse.status));
  assert.equal(
    compatibilityResponse.headers.get("location"),
    "http://localhost/calculators/superelevation?entitlement=pro&sample=1",
  );
});

test("renders public legal pages and branded signed-out account access", async () => {
  const [termsResponse, privacyResponse, accountResponse, loginResponse] = await Promise.all([
    render("/terms"),
    render("/privacy"),
    render("/account"),
    render("/login"),
  ]);
  assert.equal(termsResponse.status, 200);
  assert.equal(privacyResponse.status, 200);
  assert.equal(accountResponse.status, 200);
  assert.equal(loginResponse.status, 200);
  const [terms, privacy, account, login] = await Promise.all([
    termsResponse.text(),
    privacyResponse.text(),
    accountResponse.text(),
    loginResponse.text(),
  ]);
  assert.match(terms, /\$29 USD per month/i);
  assert.match(terms, /renews automatically/i);
  assert.match(terms, /nonrefundable/i);
  assert.match(terms, /licensed professional responsible for the project/i);
  assert.match(privacy, /not automatically uploaded/i);
  assert.match(privacy, /Stripe directly processes/i);
  assert.match(privacy, /Provider and WorkOS process/i);
  assert.match(account, /Sign in to manage Pro/i);
  assert.match(account, /Sign in securely/i);
  assert.match(account, /Keep calculating free/i);
  assert.match(login, /Sign in to Superelevation Calculator/i);
  assert.match(login, /work email, Microsoft account, or Google account/i);
  assert.match(login, /Sign-in setup is in progress/i);
  assert.match(login, /Engineering files and calculations stay on this device/i);
  assert.doesNotMatch(`${account}${login}`, /ChatGPT|OpenAI account|Sign in with WorkOS/i);
});

test("uses WorkOS identity without coupling billing access to email", async () => {
  const [productAuth, proxy, signIn, callback, identity] = await Promise.all([
    readFile(new URL("../app/product-auth.ts", import.meta.url), "utf8"),
    readFile(new URL("../proxy.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/auth/sign-in/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/auth/callback/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../lib/billing/identity.ts", import.meta.url), "utf8"),
  ]);
  assert.match(productAuth, /withAuth/);
  assert.match(productAuth, /provider: "workos"/);
  assert.match(proxy, /authkitProxy/);
  assert.match(signIn, /getSignInUrl/);
  assert.match(callback, /handleAuth/);
  assert.match(identity, /user\.provider.*user\.subject/s);
  assert.doesNotMatch(identity, /user\.email/);
  assert.doesNotMatch(`${productAuth}${proxy}${signIn}${callback}`, /oai-authenticated|signin-with-chatgpt|getChatGPTUser/i);
});

test("protects complimentary Pro administration with a stable WorkOS allowlist", async () => {
  const [page, client, route, adminAuth, entitlementRoute, accountPage, accountClient] = await Promise.all([
    readFile(new URL("../app/admin/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/admin/AdminEntitlementsClient.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/api/admin/entitlements/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../lib/auth/admin.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/api/entitlement/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/account/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/account/AccountClient.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(page, /isProductAdmin/);
  assert.match(page, /redirect\("\/login\?return_to=%2Fadmin"\)/);
  assert.match(client, /Grant complimentary Pro/);
  assert.match(client, /Revoke Pro access/);
  assert.match(client, /exact verified work email/i);
  assert.match(client, /activates after the first matching WorkOS sign-in/i);
  assert.match(client, /customer Terms and Privacy acceptance is already on file/i);
  assert.match(route, /requireSameOrigin/);
  assert.match(route, /acceptance_confirmed/);
  assert.match(route, /grantManualPro/);
  assert.match(route, /revokeManualPro/);
  assert.match(route, /grantPreauthorizedPro/);
  assert.match(route, /revokePreauthorizedPro/);
  assert.match(adminAuth, /ADMIN_WORKOS_USER_IDS/);
  assert.match(adminAuth, /user\.subject/);
  assert.doesNotMatch(adminAuth, /user\.email/);
  assert.match(entitlementRoute, /manual-grant/);
  assert.match(entitlementRoute, /preauthorized-email/);
  assert.match(entitlementRoute, /claimActivePreauthorizedEntitlement/);
  assert.match(accountPage, /isProductAdmin\(user\).*href="\/admin"/s);
  assert.match(accountClient, /Complimentary Pro/);
  assert.match(accountClient, /Preauthorized Pro/);
  assert.match(accountClient, /AbortSignal\.timeout\(10_000\)/);
  assert.match(accountClient, /Account status is temporarily unavailable/);
  assert.match(accountClient, /Retry account check/);
  assert.match(accountClient, /No calculator inputs, results, or project files were changed/);
  assert.match(accountClient, /isPro && account\.billing\.subscription_status/);
});

test("records bounded anonymous calculator usage for the protected admin dashboard", async () => {
  const [events, tracker, store, analyticsRoute, adminRoute, adminClient, privacy] = await Promise.all([
    readFile(new URL("../lib/analytics/events.ts", import.meta.url), "utf8"),
    readFile(new URL("../lib/analytics/client.ts", import.meta.url), "utf8"),
    readFile(new URL("../lib/analytics/store.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/api/analytics/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/api/admin/analytics/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/admin/AdminAnalyticsClient.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/privacy/page.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(events, /ALLOWED_KEYS.*session_token.*calculator.*event.*detail/s);
  assert.doesNotMatch(events, /project_name|station|radius|result/i);
  assert.match(tracker, /sessionStorage/);
  assert.match(tracker, /navigator\.doNotTrack === "1"/);
  assert.match(store, /SHA-256/);
  assert.match(store, /'-90 days'/);
  assert.match(analyticsRoute, /requireSameOrigin/);
  assert.match(adminRoute, /isProductAdmin/);
  assert.match(adminClient, /Calculator usage/);
  assert.match(adminClient, /No project names, engineering inputs/);
  assert.match(privacy, /Privacy-preserving product analytics/);
});

test("payment activation is webhook-driven and does not grant from the success redirect", async () => {
  const [checkout, webhook, account, remoteEntitlement, signingSource, publicKey] = await Promise.all([
    readFile(new URL("../app/api/billing/checkout/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/api/stripe/webhook/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/account/AccountClient.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/entitlements.ts", import.meta.url), "utf8"),
    readFile(new URL("../lib/billing/entitlement-token.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/entitlement-public-key.json", import.meta.url), "utf8"),
  ]);
  assert.match(checkout, /verifyConfiguredProPrice/);
  assert.match(checkout, /recordLegalAcceptance/);
  assert.match(checkout, /checkout_attempt_id/);
  assert.match(checkout, /idempotencyKey: `checkout:\$\{id\}:\$\{body\.checkout_attempt_id\}`/);
  assert.match(checkout, /success_url: `\$\{origin\}\/account\?checkout=success`/);
  assert.doesNotMatch(checkout, /setEntitlement|upsertSubscription/);
  assert.match(webhook, /constructEventAsync/);
  assert.match(webhook, /Stripe\.createSubtleCryptoProvider/);
  assert.match(webhook, /hasProcessedStripeEvent/);
  assert.match(webhook, /upsertSubscription/);
  assert.match(account, /Activating Pro/);
  assert.match(account, /do not pay again/i);
  assert.match(remoteEntitlement, /cached-offline-grace/);
  assert.match(remoteEntitlement, /fails closed to Free/i);
  assert.match(remoteEntitlement, /crypto\.subtle\.verify/);
  assert.match(remoteEntitlement, /entitlement-public-key\.json/);
  assert.match(remoteEntitlement, /localSnapshot\(this\.manifest, "free", unsignedSnapshot\.status\)/);
  assert.match(signingSource, /privateJwk\.alg = "EdDSA"/);
  assert.equal(JSON.parse(publicKey).alg, "EdDSA");
});

test("ships the Python worker and shared runtime manifest", async () => {
  const [worker, manifest] = await Promise.all([
    readFile(new URL("../public/pyodide-worker.js", import.meta.url), "utf8"),
    readFile(new URL("../public/python/manifest.json", import.meta.url), "utf8"),
  ]);
  assert.match(worker, /PYODIDE_VERSION = "0\.29\.4"/);
  assert.match(worker, /bundle\.pyodide_packages/);
  assert.match(worker, /bundle\.micropip_packages/);
  assert.match(worker, /vericivil_service\.dispatch_safe/);
  assert.match(manifest, /crushed_stone_base/);
  assert.match(manifest, /reportlab==4\.4\.7/);
  assert.match(manifest, /ezdxf==1\.4\.4/);
  assert.match(manifest, /"pyodide_packages": \[\]/);
  assert.match(manifest, /super_service\.py/);
  assert.match(manifest, /commercial_entitlements\.py/);
  await assert.rejects(access(new URL("../app/_sites-preview", import.meta.url)));
});

test("debounces automatic calculations when required inputs are ready", async () => {
  const source = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  assert.match(source, /AUTO_CALC_DELAY_MS = 450/);
  assert.match(source, /Calculates automatically/);
  assert.match(source, /setTimeout\(async \(\) =>/);
});

test("recalculates after reapplying an identical LandXML preset", async () => {
  const source = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  assert.match(source, /const \[calculationRequest, setCalculationRequest\] = useState\(0\)/);
  assert.match(source, /setCalculationRequest\(\(request\) => request \+ 1\)/);
  assert.match(source, /\[calculationKey, calculationRequest, runtime, call, entitlement\]/);
});

test("preserves coordinated reverse-curve results when a saved curve is selected", async () => {
  const source = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  assert.match(source, /loadedCurveCalculation = useRef/);
  assert.match(source, /loadedCurve\?\.key === calculationKey && loadedCurve\.request === calculationRequest/);
  assert.match(source, /loadedCurveCalculation\.current = \{ key: calculationInputKey\(nextInputs\), request: calculationRequest \}/);
  assert.match(source, /A saved corridor curve may include reverse-curve coordination metadata/);
  assert.doesNotMatch(source, /return curves\.map\(\(curve, index\) => index === selectedCurve/);
});

test("opens a save picker for exports with a download fallback", async () => {
  const source = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  assert.match(source, /showSaveFilePicker/);
  assert.match(source, /suggestedName: name/);
  assert.match(source, /createWritable/);
  assert.match(source, /if \(!picker\) return "download"/);
  assert.match(source, /Superelevation project/);
  assert.match(source, /Project \$\{outcome\}/);
  assert.doesNotMatch(source, />Detail DXF</);
});

test("renders lookup results as labeled engineering content instead of JSON", async () => {
  const source = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  assert.match(source, /lookup-output/);
  assert.match(source, /Full-super range|match\.label/);
  assert.doesNotMatch(source, /JSON\.stringify\(lookupResult/);
});

test("uses the dark engineering workspace theme", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /color-scheme: dark/);
  assert.match(css, /--paper: #07100e/);
  assert.match(css, /\.lookup-card/);
});

test("shows concise guidance for invalid project files", async () => {
  const source = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  assert.match(source, /Use Select LandXML to open XML alignment files/);
  assert.match(source, /The selected project file is empty/);
});

test("defaults embedded LandXML projects to the first curve", async () => {
  const source = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  assert.match(source, /const hasLandxmlCurves/);
  assert.match(source, /landxml_curve_index\) === 0/);
  assert.match(source, /loadCurveFrom\(restoredCurves\[firstLandxmlCurve\], firstLandxmlCurve/);
  assert.match(source, /applyPreset\(0, loaded\.landxml\)/);
});

test("ships interactive diagram zoom and corridor QA controls", async () => {
  const source = await readFile(new URL("../app/SuperelevationAnalysis.tsx", import.meta.url), "utf8");
  const planSource = await readFile(new URL("../app/SuperelevationPlanView.tsx", import.meta.url), "utf8");
  const appSource = await readFile(new URL("../app/CalculatorApp.tsx", import.meta.url), "utf8");
  assert.match(source, /addEventListener\("wheel", wheelZoom, \{ passive: false \}\)/);
  assert.match(source, /event\.preventDefault\(\)/);
  assert.match(source, /Pan toward corridor start/);
  assert.match(source, /onPointerMove={movePan}/);
  assert.match(source, /onClick={selectPoint}/);
  assert.match(source, /Array\.from\(\{ length: 721 \}/);
  assert.match(source, /Math\.min\(\(activeDomain\[1\] - activeDomain\[0\]\).*5\)/);
  assert.match(source, /Open large analysis view/);
  assert.match(source, /Plan View/);
  assert.match(planSource, /plan\.entities/);
  assert.match(planSource, /entity\.type === "LINE"/);
  assert.match(planSource, /entity\.type === "TEXT"/);
  assert.match(planSource, /rotate\(/);
  assert.match(planSource, /textAnchor/);
  assert.match(planSource, /cadColor/);
  assert.match(planSource, /selectedGroup/);
  assert.match(planSource, /const payloadKey = JSON\.stringify/);
  assert.match(planSource, /plan\.bounds/);
  assert.match(planSource, /plan\.entities/);
  assert.match(planSource, /<PlanCanvas key={payloadKey}/);
  assert.match(planSource, /plan\.errors\.map|plan\.errors \|\| \[\]/);
  assert.match(planSource, /plan\.warnings\.map|plan\.warnings \|\| \[\]/);
  assert.match(planSource, /cadFontFamily\(entity\.text_style\)/);
  assert.match(planSource, /\["ENGINEERING REGULAR", "ENGINEERING"\]\.includes\(normalized\)/);
  assert.match(planSource, /Arial Narrow/);
  assert.doesNotMatch(source, /plan\.events/);
  assert.match(planSource, /getScreenCTM\(\)/);
  assert.match(planSource, /matrix\.inverse\(\)/);
  assert.match(planSource, /clientPointToDrawing/);
  assert.match(planSource, /className="cad-hit-target"/);
  assert.match(planSource, /pointerEvents="stroke"/);
  assert.doesNotMatch(planSource, /className="plan-event/);
  assert.doesNotMatch(planSource, /plan\.curve_paths/);
  assert.match(planSource, /addEventListener\("wheel", wheelZoom, \{ passive: false \}\)/);
  assert.match(planSource, /onPointerMove={movePan}/);
  assert.match(source, /diagrams\.flatMap/);
  assert.match(appSource, /No LandXML curve selected/);
  assert.match(appSource, /excluded_landxml_curve_indexes/);
  assert.match(appSource, /const removeCurve/);
  assert.match(appSource, /index === selectedCurve/);
  assert.match(appSource, /results: calculation\.results/);
  assert.match(source, /Zoom in/);
  assert.match(source, /Reset zoom/);
  assert.match(source, /Snap events/);
  assert.match(source, /Corridor QA/);
  assert.match(appSource, /diagram_lookup/);
  assert.match(appSource, /corridor_diagram/);
  assert.match(appSource, /plan_view/);
});
