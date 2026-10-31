const { app, dialog, Menu, nativeTheme } = require('electron');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');

app.setPath('userData', process.env.VERICIVIL_TEST_PROFILE);
const nativeQuestion = dialog.showMessageBoxSync;
dialog.showMessageBoxSync = (window, options) => options?.message === 'Switch tools and discard unsaved changes?' ? 1 : nativeQuestion(window, options);
const root = path.resolve(__dirname, '../..');
const out = path.join(root, 'local/typicals');
const timer = setTimeout(() => { console.error('Typicals offline acceptance timed out'); app.exit(1); }, 150000);

require('../app/main.cjs').start().then(async window => {
  const evaluate = async code => {
    try { return await window.webContents.executeJavaScript(code); }
    catch (error) { console.error('Failed script:', code); throw error; }
  };
  const waitFor = async code => {
    for (let n = 0; n < 800; n++) { if (await evaluate(code)) return; await new Promise(resolve => setTimeout(resolve, 100)); }
    throw new Error(`Timed out: ${code}`);
  };
  const click = text => evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent===${JSON.stringify(text)}).click()`);
  const captureCad = async name => {
    window.show(); window.focus();
    for (let attempt = 0; attempt < 20; attempt++) {
      await evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))");
      const bounds = await evaluate("(()=>{const r=document.querySelector('.typicals-canvas').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,viewport:innerWidth}})()");
      const frame = await window.webContents.capturePage();
      const scale = frame.getSize().width / bounds.viewport;
      const crop = frame.crop({ x: Math.round(bounds.x * scale), y: Math.round(bounds.y * scale), width: Math.round(bounds.width * scale), height: Math.round(bounds.height * scale) });
      const bytes = crop.toBitmap(); let visible = 0;
      // Synthetic TS_TEST_GEOMETRY is #00aa66; count linework inside the canvas, excluding its legend.
      for (let i = 0; i < bytes.length; i += 4) if (bytes[i + 2] < 40 && bytes[i + 1] > 140 && bytes[i] > 60 && bytes[i] < 130) visible++;
      if (visible > 300) { await writeFile(path.join(out, name), frame.toPNG()); return; }
      await new Promise(resolve => setTimeout(resolve, 150));
    }
    throw new Error('CAD capture has no painted section linework: ' + name);
  };
  await mkdir(out, { recursive: true });
  window.webContents.setBackgroundThrottling(false);
  window.webContents.on('console-message', event => { if (event.level >= 2 || event.level === 'error') console.log('Renderer:', event.message); });
  await waitFor("!!document.querySelector('.desktop-workspace')");
  // Native switching waits for the existing tool to finish initializing.
  await waitFor("!!document.querySelector('.desktop-runtime.ready')");
  await new Promise(resolve => setTimeout(resolve, 100));
  console.log('Superelevation ready; switching through native Tools menu.');
  Menu.getApplicationMenu().items.find(v => v.label === 'Tools').submenu.items[1].click();
  await waitFor("!!document.querySelector('.typicals-canvas')");
  assert.equal(await evaluate("window.location.hash"), '#typicals');
  assert.equal(await evaluate("document.querySelector('h1').textContent"), 'VeriCivil Typicals');
  assert.equal(await evaluate("Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Export DXF').disabled"), true);
  const setWidth = width => evaluate(`(()=>{const input=Array.from(document.querySelectorAll('label')).find(l=>l.firstChild?.textContent==='Lane width (ft)').querySelector('input');input.focus();input.value='${width}';input.dispatchEvent(new Event('input',{bubbles:true}));input.blur();})()`);
  await setWidth(11);
  await waitFor("document.querySelector('[data-component=left_lane] line')?.getAttribute('x2')==='-11'");
  assert.equal(await evaluate("document.querySelector('[data-component=left_shoulder] line').getAttribute('x2')"), '-17');
  await click('Undo');
  await waitFor("document.querySelector('[data-component=left_lane] line')?.getAttribute('x2')==='-12'");
  await click('Redo');
  await waitFor("document.querySelector('[data-component=left_lane] line')?.getAttribute('x2')==='-11'");
  await evaluate("Array.from(document.querySelectorAll('.typicals-point')).find(l=>l.textContent.includes('Lock left_shoulder')).querySelector('input').click()");
  await waitFor("!document.querySelector('fieldset').disabled");
  await setWidth(10);
  await waitFor("document.querySelector('[role=alert]')?.textContent.includes('Constraint conflict')");
  assert.equal(await evaluate("document.querySelector('[data-component=left_lane] line').getAttribute('x2')"), '-11');
  await click('Dismiss');
  console.log('PASS: actual UI geometry propagation, undo/redo and atomic point-lock conflict rejection.');

  const python = process.platform === 'win32' ? 'python' : 'python3';
  const project = execFileSync(python, ['-c', 'import json; from test_typicals import mapped_project; print(json.dumps(mapped_project()))'], { cwd: root, encoding: 'utf8' });
  const fixture = path.join(out, 'synthetic-mapped.typicals.json');
  await writeFile(fixture, project);
  dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [fixture] });
  dialog.showSaveDialog = async (_window, options) => ({ canceled: false, filePath: path.join(out, path.basename(options.defaultPath)) });
  await evaluate("void (window.confirm=()=>true)");
  await evaluate("window.vericivilDesktop.openProjectDialog()");
  await waitFor("!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Export DXF').disabled");
  assert.equal(await evaluate("document.querySelectorAll('.typicals-levelbar input').length"), 3);
  await evaluate("document.querySelector('.typicals-levelbar input').click()");
  await waitFor("!document.querySelector('[data-component=left_lane] line')");
  assert.equal(await evaluate("!!document.querySelector('[data-component=ground] line')"), true);
  await evaluate("document.querySelector('.typicals-levelbar input').click()");
  await waitFor("!!document.querySelector('[data-component=left_lane] line')");
  await click('Save project…');
  await waitFor("document.querySelector('[role=status]')?.textContent.includes('Project saved')");
  assert.equal(JSON.parse(await readFile(fixture, 'utf8')).format, 'vericivil.typicals');
  for (const format of ['DXF', 'SVG', 'PDF']) {
    await click('Export ' + format);
    await waitFor(`document.querySelector('[role=status]')?.textContent==='${format} exported'`);
  }
  assert.match((await readFile(path.join(out, 'typical-section.pdf'))).toString('ascii', 0, 8), /%PDF/);
  assert.match(await readFile(path.join(out, 'typical-section.svg'), 'utf8'), /width="17in"/);
  assert.match(await readFile(path.join(out, 'typical-section.dxf'), 'utf8'), /TS_TEST_GEOMETRY/);
  assert.match(await evaluate("document.querySelector('.typicals-report').textContent"), /DIMENSION/);
  await click('Save export report…');
  await waitFor("document.querySelector('[role=status]')?.textContent==='DXF report saved'");
  await readFile(path.join(out, 'typical-section-report.txt'));
  console.log('PASS: native project reopen/save, imported catalog mapping, editable DXF, PDF/SVG and report saves in offline Electron.');
  const oldStyles = await evaluate("Array.from(document.querySelectorAll('.typicals-levelbar i')).map(n=>n.style.background)");
  await click('Sheet');
  await evaluate("Array.from(document.querySelectorAll('label')).find(l=>l.textContent.includes('Monochrome print')).querySelector('input').click()");
  await waitFor("!document.querySelector('fieldset').disabled");
  assert.deepEqual(await evaluate("Array.from(document.querySelectorAll('.typicals-levelbar i')).map(n=>n.style.background)"), oldStyles);
  await evaluate("Array.from(document.querySelectorAll('label')).find(l=>l.textContent.includes('Monochrome print')).querySelector('input').click()");
  await waitFor("!document.querySelector('fieldset').disabled");
  await click('Section');
  await click('Fit');
  nativeTheme.themeSource = 'dark';
  await waitFor("matchMedia('(prefers-color-scheme: dark)').matches");
  await captureCad('cad-dark.png');
  nativeTheme.themeSource = 'light';
  await waitFor("!matchMedia('(prefers-color-scheme: dark)').matches");
  await captureCad('cad-light.png');
  await click('Engineering print');
  await waitFor("!!document.querySelector('.typicals-sheet svg')");
  await writeFile(path.join(out, 'print-preview.png'), (await window.webContents.capturePage()).toPNG());
  window.setSize(1040, 800);
  await new Promise(resolve => setTimeout(resolve, 250));
  await writeFile(path.join(out, 'laptop-print.png'), (await window.webContents.capturePage()).toPNG());
  console.log('PASS: CAD color/print independence; painted dark/light/print/laptop captures saved.');
  clearTimeout(timer);
  app.exit(0);
}).catch(error => { console.error(error); clearTimeout(timer); app.exit(1); });
