const assert = require('node:assert/strict');
const { app, BrowserWindow, dialog, nativeTheme } = require('electron');
const { mkdtempSync, writeFileSync, mkdirSync, rmSync } = require('node:fs');
const { execFileSync } = require('node:child_process');
const { tmpdir } = require('node:os');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const profile = mkdtempSync(path.join(tmpdir(), 'vericivil-section-'));
app.setPath('userData', profile);
const timer = setTimeout(() => app.exit(1), 120000);
app.on('quit', () => rmSync(profile, { recursive: true, force: true }));
const capture = process.env.VERICIVIL_CAPTURE_DIR;
if (capture) mkdirSync(capture, { recursive: true });

const browserUrl = process.env.VERICIVIL_BROWSER_URL;
const launch = browserUrl ? app.whenReady().then(async () => {
  const window = new BrowserWindow({ width: 1440, height: 960, webPreferences: { partition: 'section-browser-test', sandbox: true, contextIsolation: true, nodeIntegration: false } });
  await window.loadURL(browserUrl);
  return window;
}) : require('../app/main.cjs').start();
launch.then(async window => {
  window.webContents.setBackgroundThrottling(false);
  const js = code => window.webContents.executeJavaScript(code);
  const wait = async code => {
    for (let attempt = 0; attempt < 250; attempt++) {
      if (await js(code)) return;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    console.error(await js("document.querySelector('.cross-section-view')?.innerText || document.body.innerText.slice(-1200)"));
    console.error(await js('JSON.stringify({requests:window.sectionRequests,input:document.querySelector(".cross-section-station input")?.value,active:document.activeElement?.tagName})'));
    throw new Error(`Timed out: ${code}`);
  };
  await wait(browserUrl ? "document.querySelector('.privacy-strip .version')?.textContent.includes('1.7.3')" : "!!document.querySelector('.desktop-runtime.ready')");
  const python = process.platform === 'win32' ? 'python' : 'python3';
  const fixture = JSON.parse(execFileSync(python, ['-c', `
import json, super_service
values = {"criteria_profile":"aashto-green-book-2018-2019-10","project_name":"Synthetic cross-section acceptance","pc":"1000","pt":"2000","speed":"60","radius":"2000","e_manual":"0.06","area":"rural","runoff_tangent_percent":"70","normal_crown":"0.02","lane_widths":"12,12,12,12","rotation_axis":"centerline","curve_direction":"left"}
result = super_service.calculate_curve(values)["results"]
ramp_values = {**values,"pc":"5000","pt":"6000","roadway":"one_way","initial_section":"single_slope","initial_slope":"0.02","lane_widths":"11,11,11","rotation_axis":"right_edge","curve_direction":"right"}
ramp = super_service.calculate_curve(ramp_values)["results"]
curves = [{"results":result,"meta":{"curve_direction":"left","curve_name":"Synthetic four-lane undivided"}}, {"results":ramp,"meta":{"curve_direction":"right","curve_name":"Synthetic three-lane ramp"}}]
content = super_service.project_save({"version":5,"vars":values,"curves":curves,"last_results":result,"last_meta":curves[0]["meta"]})
print(json.dumps({"content":content,"full":result["full_super_ft"]}))
`], { cwd: root, encoding: 'utf8' }));
  const project = path.join(profile, 'section.vericivil');
  writeFileSync(project, fixture.content);
  if (browserUrl) {
    window.webContents.debugger.attach('1.3');
    const { root: document } = await window.webContents.debugger.sendCommand('DOM.getDocument');
    const { nodeId } = await window.webContents.debugger.sendCommand('DOM.querySelector', { nodeId: document.nodeId, selector: 'input[type=file][accept*=".vericivil"]' });
    await window.webContents.debugger.sendCommand('DOM.setFileInputFiles', { nodeId, files: [project] });
  } else {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [project] });
    await js('window.vericivilDesktop.openProjectDialog()');
  }
  await wait("document.querySelectorAll('.lane-tables h4').length===4");
  await wait("Array.from(document.querySelectorAll('[role=tab]')).some(button=>button.textContent==='Cross Section')");
  await js("Array.from(document.querySelectorAll('[role=tab]')).find(button=>button.textContent==='Cross Section').click()");
  await wait("document.querySelectorAll('.cross-section-drawing .section-segment').length===4 && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'");
  await js("document.querySelector('.expand-analysis').click()");
  const station = () => js("Number(document.querySelector('[aria-label=\"Cross-section station scrubber\"]').value)");
  console.log('Loaded four-lane section; checking native input.');
  await js("window.sectionRequests=[]; var sectionPost=Worker.prototype.postMessage; Worker.prototype.postMessage=function(message,...args){if(message.operation==='diagram_lookup')window.sectionRequests.push(message.payload.station);return sectionPost.call(this,message,...args)};undefined;");
  const before = await station();
  await js("document.querySelector('[aria-label=\"Cross-section station scrubber\"]').focus()");
  window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Right' });
  window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Right' });
  await wait(`Number(document.querySelector('[aria-label="Cross-section station scrubber"]').value)===${before + 1} && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'`);
  const enter = async text => {
    window.focus();
    window.webContents.focus();
    await js("var input=document.querySelector('[aria-label=\"Cross-section station\"]'); input.focus(); input.select();");
    window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Backspace' });
    window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Backspace' });
    for (const character of text) window.webContents.sendInputEvent({ type: 'char', keyCode: character });
    await wait(`document.querySelector('[aria-label="Cross-section station"]').value===${JSON.stringify(text)}`);
    await js('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
    await js("document.querySelector('.cross-section-station button').click()");
  };
  await enter(String(fixture.full));
  await wait(`Number(document.querySelector('[aria-label="Cross-section station scrubber"]').value)===${fixture.full} && document.querySelectorAll('.cross-section-drawing .section-segment').length===4`);
  console.log('Station entry propagated to the section.');
  const rise = () => js("(() => {const line=document.querySelector('.section-segment line');return Math.abs(Number(line.getAttribute('y1'))-Number(line.getAttribute('y2')));})()");
  const exaggerated = await rise();
  await js("document.querySelector('.cross-section-scale input').click()");
  const actual = await rise();
  assert.ok(Math.abs(exaggerated / actual - 5) < 1e-10, 'true-scale toggle changes only vertical exaggeration');
  await js("document.querySelector('.cross-section-scale input').click()");
  await enter('-100');
  await wait("!!document.querySelector('.cross-section-error')");
  assert.match(await js("document.querySelector('.cross-section-error').textContent"), /within this curve/);
  await js("document.querySelector('[aria-label=\"Previous section event\"]').click()");
  await wait("!document.querySelector('.cross-section-error') && document.querySelectorAll('.cross-section-drawing .section-segment').length===4");
  const beforeWheel = await station();
  await js("var slider=document.querySelector('[aria-label=\"Cross-section station scrubber\"]'); slider.focus(); slider.dispatchEvent(new WheelEvent('wheel',{deltaY:10,bubbles:true,cancelable:true}));");
  await wait(`Number(document.querySelector('[aria-label="Cross-section station scrubber"]').value)===${beforeWheel + 1} && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'`);
  await js("var curve=document.querySelector('[aria-label=\"Cross-section curve\"]'); curve.value='1'; curve.dispatchEvent(new Event('change',{bubbles:true}));");
  await wait("document.querySelectorAll('.cross-section-drawing .section-segment').length===3 && document.querySelector('.cross-section-heading h4').textContent==='One-way / ramp'");
  assert.ok(await station() > 4000, 'switching curves clamps station into its own domain instead of bridging the gap');
  await js("var curve=document.querySelector('[aria-label=\"Cross-section curve\"]'); curve.value='0'; curve.dispatchEvent(new Event('change',{bubbles:true}));");
  await wait("document.querySelectorAll('.cross-section-drawing .section-segment').length===4");
  await enter('1000');
  await wait("Number(document.querySelector('[aria-label=\"Cross-section station scrubber\"]').value)===1000 && document.querySelectorAll('.cross-section-drawing .section-segment').length===4");
  for (const theme of browserUrl ? ['desktop', 'mobile'] : ['light', 'dark']) {
    if (!browserUrl) nativeTheme.themeSource = theme;
    window.setSize(theme === 'mobile' ? 414 : 1440, theme === 'mobile' ? 896 : 960);
    if (!browserUrl) await wait(`getComputedStyle(document.documentElement).getPropertyValue('--paper').trim()==='${theme === 'light' ? '#eef3f1' : '#0e1714'}'`);
    await new Promise(resolve => setTimeout(resolve, 200));
    assert.equal(await js('document.documentElement.scrollWidth<=innerWidth'), true);
    if (capture) {
      await js("document.querySelector('.cross-section-view').scrollTop=0");
      writeFileSync(path.join(capture, `cross-section-${browserUrl ? 'browser' : 'electron'}-${theme}.png`), (await window.capturePage()).toPNG());
      await js("var section=document.querySelector('.cross-section-view'); section.scrollTop=section.scrollHeight");
      await js('new Promise(resolve=>requestAnimationFrame(resolve))');
      writeFileSync(path.join(capture, `cross-section-${browserUrl ? 'browser' : 'electron'}-${theme}-lower.png`), (await window.capturePage()).toPNG());
      await js("document.querySelector('.cross-section-view').scrollTop=0");
    }
  }
  await js("document.querySelector('.expand-analysis').click(); Array.from(document.querySelectorAll('[role=tab]')).find(button=>button.textContent==='Diagram').click()");
  await wait("!!document.querySelector('.chart-canvas')");
  assert.equal(await js("!!document.querySelector('.diagram-inspector .inspector-lanes')"), true, 'section station is shared with diagram');
  await js('window.confirm=()=>true;undefined;');
  if (browserUrl) {
    writeFileSync(project, execFileSync(python, ['-c', `
import super_service
values={"pc":"1000","pt":"2000","speed":"45","radius":"1200","curve_direction":"left","project_name":"Synthetic MDOT schematic"}
result=super_service.calculate_curve(values)["results"]
print(super_service.project_save({"version":5,"vars":values,"curves":[],"last_results":result,"last_meta":{"curve_direction":"left"}}))
`], { cwd: root, encoding: 'utf8' }));
    const { root: document } = await window.webContents.debugger.sendCommand('DOM.getDocument');
    const { nodeId } = await window.webContents.debugger.sendCommand('DOM.querySelector', { nodeId: document.nodeId, selector: 'input[type=file][accept*=".vericivil"]' });
    await window.webContents.debugger.sendCommand('DOM.setFileInputFiles', { nodeId, files: [] });
    await window.webContents.debugger.sendCommand('DOM.setFileInputFiles', { nodeId, files: [project] });
  } else await js("Array.from(document.querySelectorAll('button')).find(button=>button.textContent==='Load synthetic sample').click()");
  await wait("document.querySelectorAll('.lane-tables h4').length===2");
  await js("Array.from(document.querySelectorAll('[role=tab]')).find(button=>button.textContent==='Cross Section').click()");
  await wait("document.querySelector('.cross-section-heading h4')?.textContent==='Left/right slope schematic' && document.querySelectorAll('.cross-section-drawing .section-segment').length===2");
  assert.equal(await js("!!document.querySelector('.section-pivot') || !!document.querySelector('.cross-section-scale')"), false);
  assert.match(await js("document.querySelector('.cross-section-drawing svg').getAttribute('aria-label')"), /Left slope plane:.*Right slope plane:/);
  console.log(`PASS: ${browserUrl ? 'browser' : 'offline Electron'} geometry, native keyboard/station input, focused wheel, curve-domain switching, scale, invalid entry recovery, schematic limits/accessibility, captures and shared inspector.`);
  clearTimeout(timer);
  app.exit(0);
}).catch(error => { console.error(error); clearTimeout(timer); app.exit(1); });
