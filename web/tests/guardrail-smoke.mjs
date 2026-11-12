// Run with: env -u ELECTRON_RUN_AS_NODE web/node_modules/.bin/electron web/tests/guardrail-smoke.mjs
import assert from "node:assert/strict";
import { app, BrowserWindow } from "electron";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const temp = mkdtempSync(path.join(tmpdir(), "guardrail-smoke-"));
const capture = path.join(root, ".impeccable/review/guardrail");
mkdirSync(capture, { recursive: true });
app.setPath("userData", path.join(temp, "profile"));
const timer = setTimeout(() => { console.error("Guardrail smoke timed out."); app.exit(1); }, 180000);

app.whenReady().then(async () => {
  const window = new BrowserWindow({ width: 1440, height: 1000, useContentSize: true, show: false,
    webPreferences: { partition: "guardrail-test", contextIsolation: true, nodeIntegration: false, sandbox: true } });
  const js = code => window.webContents.executeJavaScript(code);
  const errors = [];
  window.webContents.on("console-message", event => { if (event.level === "error") errors.push(event.message); });
  const wait = async code => {
    for (let n = 0; n < 600; n++) {
      if (await js(`Boolean(${code})`)) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`Timed out: ${code}\n${await js("document.body.innerText")}\n${errors.join("\n")}`);
  };
  const change = (name, value) => js(`(() => {
    const field = document.querySelector('[name="${name}"]');
    const prototype = field.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(field, ${JSON.stringify(value)});
    field.dispatchEvent(new Event(field.tagName === 'SELECT' ? 'change' : 'input', {bubbles:true}));
  })()`);
  const button = text => `Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes(${JSON.stringify(text)}))`;
  const downloads = [];
  window.webContents.session.on("will-download", (_, item) => {
    const destination = path.join(temp, `${downloads.length}-${item.getFilename()}`);
    item.setSavePath(destination);
    const record = { destination, done: false, state: "" };
    downloads.push(record);
    item.once("done", (_, state) => { record.state = state; record.done = true; });
  });
  const takeDownload = async text => {
    const index = downloads.length;
    await js(`${button(text)}.click()`);
    for (let n = 0; n < 600; n++) {
      if (downloads[index]?.done) {
        assert.equal(downloads[index].state, "completed");
        return readFileSync(downloads[index].destination);
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`Download failed: ${text}\n${await js("document.body.innerText")}`);
  };
  const open = content => js(`(() => {
    const input = document.querySelector('input[type=file]');
    const transfer = new DataTransfer();
    transfer.items.add(new File([${JSON.stringify(content)}], 'guardrail.json', {type:'application/json'}));
    input.files = transfer.files; input.dispatchEvent(new Event('change', {bubbles:true}));
  })()`);
  await window.loadURL(process.env.GUARDRAIL_TEST_URL || "http://localhost:3001/calculators/guardrail");
  await wait("document.querySelector('.guardrail-runtime.ready') && document.querySelector('.guardrail-results')");
  assert.ok((await js("document.querySelector('.guardrail-results').innerText")).includes("130.6458"));
  // Exercise same-document Back and Forward before changing the inputs.
  await js("history.pushState(history.state,'','?history=earlier'); history.pushState(history.state,'','?history=later')");
  await change("adt", "6,001");
  assert.equal(await js("!!document.querySelector('.guardrail-results')"), false, "Hide stale results immediately");
  assert.equal(await js(`${button("Download calculation PDF")}.disabled`), true);
  await wait("!!document.querySelector('.guardrail-results')");
  await js("window.confirm=()=>false; document.querySelector('a[href=\"/calculators\"]').click()");
  assert.ok((await js("location.pathname")).includes("/guardrail"));
  await js("window.guardrailPrompts=0; window.confirm=()=>{window.guardrailPrompts++;return false}; history.back()");
  await wait("window.guardrailPrompts === 1 && location.search === '?history=later'");
  assert.equal(await js("document.querySelector('[name=adt]').value"), "6,001");
  await js("window.confirm=()=>true; history.back()");
  await wait("location.search === '?history=earlier'");
  await js("window.confirm=()=>{window.guardrailPrompts++;return false}; history.forward()");
  await wait("window.guardrailPrompts === 2 && location.search === '?history=earlier'");
  assert.equal(await js("document.querySelector('[name=adt]').value"), "6,001");
  await js("window.confirm=()=>true; history.forward()");
  await wait("location.search === '?history=later'");
  await change("adt", "6,00");
  await wait("!!document.querySelector('.guardrail-error')");
  assert.equal(await js(`${button("Save project")}.disabled`), true);
  await change("adt", "6,000");
  await wait("!!document.querySelector('.guardrail-results')");
  const saved = await takeDownload("Save project");
  const document = JSON.parse(saved.toString());
  assert.equal(document.values.adt, "6,000");
  assert.equal(document.results, undefined);
  const pdf = await takeDownload("Download calculation PDF");
  assert.equal(pdf.subarray(0, 4).toString(), "%PDF");
  assert.ok(pdf.length > 100000, "Appendices must be downloaded with the report");
  writeFileSync(path.join(capture, "two-lane-package.pdf"), pdf);
  await change("facility", "divided_highway");
  await change("opposing_distance_mode", "calculated");
  await wait("document.querySelector('.guardrail-inputs').innerText.includes('98.0000')");
  await js("void (window.confirm=()=>true)");
  await open(saved.toString());
  await wait("document.querySelector('[name=facility]').value === 'two_lane_two_way' && !!document.querySelector('.guardrail-results')");
  await open('{"version":999}');
  await wait("!!document.querySelector('.guardrail-error')");
  assert.equal(await js("document.querySelector('[name=adt]').value"), "6,000", "Bad imports preserve current inputs");
  await change("adt", "6000");
  await wait("!!document.querySelector('.guardrail-results')");
  await change("clear_zone_criteria", "3r");
  assert.equal(await js("!!document.querySelector('.guardrail-results')"), false, "Changing criteria hides stale results");
  await wait("Array.from(document.querySelectorAll('.guardrail-help')).some(p=>p.textContent.includes('LA used: 14.0000 ft'))");
  const threeRSaved = await takeDownload("Save project");
  assert.equal(JSON.parse(threeRSaved.toString()).values.clear_zone_criteria, "3r");
  await change("speed", "70");
  await wait("document.querySelector('.guardrail-error')?.textContent.includes('3R clear-zone lookup')");
  assert.equal(await js(`${button("Download calculation PDF")}.disabled`), true);
  await open(threeRSaved.toString());
  await wait("document.querySelector('[name=clear_zone_criteria]').value === '3r' && !!document.querySelector('.guardrail-results')");
  writeFileSync(path.join(capture, "three-r-package.pdf"), await takeDownload("Download calculation PDF"));
  const legacy = JSON.parse(saved.toString());
  delete legacy.values.clear_zone_criteria;
  await open(JSON.stringify(legacy));
  await wait("document.querySelector('[name=clear_zone_criteria]').value === 'new_construction' && !!document.querySelector('.guardrail-results')");
  await change("clear_zone_criteria", "3r");
  await wait("!!document.querySelector('.guardrail-results')");
  await js("document.querySelector('.guardrail-project').open=true");
  await change("project", "Synthetic browser acceptance");
  await wait("!!document.querySelector('.guardrail-results')");

  for (const [name, width] of [["desktop", 1440], ["mobile", 390]]) {
    window.setContentSize(width, 1000);
    await js("document.fonts.ready.then(()=>true)");
    const height = await js("document.documentElement.scrollHeight");
    window.setContentSize(width, height);
    await js("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))");
    assert.equal(await js("document.documentElement.scrollWidth <= innerWidth"), true, `${name} has no horizontal overflow`);
    writeFileSync(path.join(capture, `${name}.png`), (await window.capturePage()).toPNG());
    if (name === "desktop") {
      const box = await js("(() => {const r=document.querySelector('.guardrail-review').getBoundingClientRect();return {x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}})()");
      writeFileSync(path.join(root, "web/public/showcase/guardrail-results.png"), (await window.capturePage(box)).toPNG());
    }
  }
  assert.deepEqual(errors, [], "No renderer errors");
  console.log("Guardrail renderer smoke passed: calculations, clear-zone criteria, 3R speed validation, legacy and current projects, PDF appendices, unsaved navigation, desktop/mobile overflow.");
  clearTimeout(timer); app.exit(0);
}).catch(error => { console.error(error); clearTimeout(timer); app.exit(1); });
app.on("quit", () => rmSync(temp, { recursive: true, force: true }));
