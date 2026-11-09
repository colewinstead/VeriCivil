const { app, dialog, nativeImage, nativeTheme } = require('electron');
const { mkdtemp, readFile, readdir, rm } = require('node:fs/promises');
const { tmpdir } = require('node:os');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { execFileSync } = require('node:child_process');
const path = require('node:path');

app.setPath('userData', process.env.VERICIVIL_TEST_PROFILE);
console.log('Starting actual Electron app and offline worker');
const root = path.resolve(__dirname, '../..');
const timer = setTimeout(() => { console.error('Desktop smoke timed out'); app.exit(1); }, 180000);
const { getEdition } = require('../edition.cjs');
const edition = getEdition();
const appDirectory = path.join(root, 'desktop', edition.appDirectory);
const original = require(path.join(appDirectory, 'main.cjs'));
original.start().then(async (window) => {
  const icon = nativeImage.createFromPath(path.join(appDirectory, 'icon.png'));
  assert.deepEqual(icon.getSize(), { width: 512, height: 512 });
  assert.equal(readFileSync(path.join(appDirectory, 'icon.png')).equals(readFileSync(path.join(root, edition.id === 'vericivil' ? 'web/public/brand/vericivil-icon.png' : 'desktop/icons/superelevation.png'))), true);
  assert.equal(app.getName(), edition.productName);
  assert.equal(await window.webContents.executeJavaScript('document.title'), edition.windowTitle);
  assert.equal(await window.webContents.executeJavaScript("document.querySelector('.desktop-toolbar h1').textContent"), edition.headerTitle);
  assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('.desktop-preview-label')"), !!edition.desktopLabel);
  assert.equal(await window.webContents.executeJavaScript('!!document.querySelector("footer")'), edition.showFooter);
  if (edition.id === 'neutral') assert.doesNotMatch(await window.webContents.executeJavaScript('document.body.innerText'), /VeriCivil|CW Aerial/);
  window.webContents.setBackgroundThrottling(false);
  window.webContents.on('console-message', (event) => console.log('Renderer:', event.message));
  const inputs = { pc: '10+00', pt: '12+00', speed: '45', radius: '1200', facility: 'centerline', area: 'rural', lane_width: '12', lanes_rotated: '2', normal_crown: '0.02', curve_direction: 'right' };
  const xml = readFileSync(path.join(root, 'tests/fixtures/compound_synthetic.xml'), 'utf8');
  const result = await window.webContents.executeJavaScript(`(async () => {
    const worker = new Worker('/pyodide-worker.js');
    const pending = new Map(); let sequence = 0;
    const ready = new Promise((resolve,reject) => {
      worker.onmessage = ({data}) => {
        if(data.type==='fatal')reject(new Error(data.message));
        if(data.type==='ready')resolve(data.manifest);
        if(data.type==='response'){
          const request=pending.get(data.id);pending.delete(data.id);
          if(data.ok)request.resolve(data.result);else request.reject(new Error(data.error.message));
        }
      };
    });
    worker.postMessage({operation:'initialize'});
    const manifest=await ready;
    const call=(operation,payload)=>new Promise((resolve,reject)=>{
      const id=++sequence;pending.set(id,{resolve,reject});
      worker.postMessage({id,operation,payload:{...payload,entitlement:{plan:'pro',status:'active'}}});
    });
    const inputs=${JSON.stringify(inputs)};
    const calculation=await call('calculate',{inputs});
    const manualCurves=[{results:calculation.results,meta:{curve_direction:'right'},notes:''}];
    const csv=await call('export_ord_csv',{curves:manualCurves});
    const pdf=await call('export_pdf',{curves:manualCurves});
    const xml=${JSON.stringify(xml)};
    const parsed=await call('parse_landxml',{content:xml,filename:'compound_synthetic.xml'});
    const curves=await call('build_all_landxml_curves',{content:xml,filename:'compound_synthetic.xml',shared_inputs:{...inputs,e_manual:'0.05',Lr_manual:'200',Lt_manual:'100'}});
    const dxf=await call('export_overlay_dxf',{curves,landxml_source:parsed.source});
    const saved=await call('project_save',{project:{version:5,vars:inputs,curves:manualCurves,last_results:calculation.results,last_meta:{curve_direction:'right'}}});
    const loaded=await call('project_load',{content:saved});
    const caseIIInputs={criteria_profile:'aashto-green-book-2018-2019-10',roadway:'divided_case_ii',
      curve_direction:'left',pc:'100+00',pt:'110+00',max_superelevation:'8',
      case_ii:Object.fromEntries(['left','right'].map(side=>[side,{speed:'65',radius:'4000',lane_count:4,lane_width:'12',
        initial_slope:side==='left'?'-0.02':'0.02',pivot_offset:side==='left'?'-12':'12',
        runoff_tangent_percent:'50',circular_placement_basis:'runoff_runout'}]))};
    const caseIICalculation=await call('calculate',{inputs:caseIIInputs});
    const caseIICurves=[{results:caseIICalculation.results,meta:{curve_direction:'left'}}];
    const caseIISaved=await call('project_save',{project:{version:6,vars:caseIIInputs,curves:caseIICurves}});
    const caseIILoaded=await call('project_load',{content:caseIISaved});
    const caseIIPdf=await call('export_pdf',{curves:caseIILoaded.project.curves});
    const caseIIDxf=await call('export_detail_dxf',{curves:caseIILoaded.project.curves});
    const sharedInputs={...caseIIInputs,radius:4000,case_ii_geometry_mode:'shared_corridor',case_ii_placement_mode:'coordinated',
      runoff_tangent_percent:50,circular_placement_basis:'runoff_runout'};
    const sharedCalculation=await call('calculate',{inputs:sharedInputs});
    const sharedSaved=await call('project_save',{project:{version:7,vars:sharedInputs,last_results:sharedCalculation.results}});
    const sharedLoaded=await call('project_load',{content:sharedSaved});
    const sharedCurves=[{results:sharedLoaded.project.last_results,meta:{curve_direction:'left'}}];
    const sharedPdf=await call('export_pdf',{curves:sharedCurves});
    const sharedDxf=await call('export_detail_dxf',{curves:sharedCurves});
    const sharedLookup=await call('diagram_lookup',{results:sharedLoaded.project.last_results,station:10192,direction:'left'});
    const adjustedRamp=await call('calculate',{inputs:{...inputs,criteria_profile:'aashto-green-book-2018-2019-10',
      roadway:'one_way',initial_section:'single_slope',initial_slope:.02,rotation_axis:'left_edge',lane_widths:'12,12',
      speed:65,radius:3000,e_manual:.06,pc:1000,pt:3000,curve_direction:'left',runoff_tangent_percent:70}});
    worker.terminate();
    let remoteBlocked=false;try{await fetch('https://vericivil.com/')}catch{remoteBlocked=true}
    return {manifest,calculation,csv:csv.content,pdf:pdf.content.slice(0,4),dxf:Array.from(dxf.content).slice(0,200),loaded,remoteBlocked,
      caseII:caseIICalculation.results.carriageways,caseIIPdf:caseIIPdf.content.slice(0,4),caseIIDxf:Array.from(caseIIDxf.content).slice(0,200),
      shared:sharedLoaded.project,sharedPdf:sharedPdf.content.slice(0,4),sharedDxf:Array.from(sharedDxf.content).slice(0,200),
      sharedLookup,adjustedRamp:adjustedRamp.results,
      rendererSecurity:{require:typeof window.require,node:typeof window.process},
      ui:document.querySelector('main')?.className};
  })()`);
  const python = process.platform === 'win32' ? 'python' : 'python3';
  const expected = JSON.parse(execFileSync(python, ['-c', 'import sys,json,super_service; print(json.dumps(super_service.dispatch("calculate",sys.stdin.read())))'], { cwd:root, input: JSON.stringify({inputs,entitlement:{plan:'pro',status:'active'}}), encoding:'utf8' }));
  assert.deepEqual(result.calculation, expected);
  assert.match(result.csv,/SuperelevationLane,Station,CrossSlope/);
  assert.equal(String.fromCharCode(...result.pdf),'%PDF');
  assert.match(Buffer.from(result.dxf).toString(),/SECTION/);
  assert.equal(result.caseII.left.friction,null);
  assert.equal(result.caseII.left.Lr,144);
  assert.equal(result.caseII.left.Lt,0);
  assert.equal(result.caseII.right.Lr,264);
  assert.equal(result.caseII.right.Lt,120);
  assert.equal(String.fromCharCode(...result.caseIIPdf),'%PDF');
  assert.match(Buffer.from(result.caseIIDxf).toString(),/SECTION/);
  assert.equal(result.shared.version,7);
  assert.equal(result.shared.vars.case_ii_geometry_mode,'shared_corridor');
  for (const [side,radius,rate,runoff] of [['left',3940,.046,156],['right',4012,.044,264]]) {
    const child=result.shared.last_results.carriageways[side];
    assert.equal(child.radius_provenance.design_radius_ft,radius);
    assert.ok(Math.abs(child.e-rate)<1e-12);
    assert.ok(Math.abs(child.Lr-runoff)<1e-9);
    assert.equal(child.full_super_ft,10192);
    assert.equal(child.full_super_out_ft,10808);
  }
  assert.equal(result.sharedLookup.cross_section.pivots.length,2);
  assert.equal(String.fromCharCode(...result.sharedPdf),'%PDF');
  assert.match(Buffer.from(result.sharedDxf).toString(),/SECTION/);
  assert.equal(result.adjustedRamp.bw,.75);
  assert.ok(Math.abs(result.adjustedRamp.Lr-216)<1e-9);
  assert.ok(Math.abs(result.adjustedRamp.Lt-72)<1e-9);
  assert.deepEqual(JSON.parse(JSON.stringify(result.loaded.project.last_results)), JSON.parse(JSON.stringify(result.calculation.results)));
  assert.equal(result.remoteBlocked,true);
  assert.deepEqual(result.rendererSecurity,{require:'undefined',node:'undefined'});
  assert.match(result.ui,/desktop-workspace/);
  for (let attempt = 0; attempt < 200; attempt++) {
    if (await window.webContents.executeJavaScript("!!document.querySelector('.desktop-recovery button:not(:disabled)')")) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('.desktop-recovery')"), true);
  await window.webContents.executeJavaScript("document.querySelector('.desktop-recovery button').click()");
  for (let attempt = 0; attempt < 200; attempt++) {
    if (await window.webContents.executeJavaScript("!document.querySelector('.desktop-recovery')")) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert.equal(await window.webContents.executeJavaScript("Array.from(document.querySelectorAll('input')).some(input => input.value === 'Recovery acceptance')"), true);
  assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('.desktop-recovery')"), false);
  console.log('PASS: startup recovery restores a saved workspace through the shared project loader.');
  const folder = await mkdtemp(path.join(tmpdir(), 'vericivil-native-dialog-'));
  const originalDialog = dialog.showSaveDialog;
  try {
    dialog.showSaveDialog = async () => ({ canceled: true });
    assert.equal(await window.webContents.executeJavaScript("window.vericivilDesktop.saveFile('project.json',new TextEncoder().encode(JSON.stringify({version:5,vars:{native_test:true}})))"), 'cancelled');
    assert.deepEqual(await readdir(folder), []);
    const destination = path.join(folder, 'project.json');
    dialog.showSaveDialog = async () => ({ canceled: false, filePath: destination });
    assert.equal(await window.webContents.executeJavaScript("window.vericivilDesktop.saveFile('project.json',new TextEncoder().encode(JSON.stringify({version:5,vars:{native_test:true}})))"), 'saved');
    assert.deepEqual(JSON.parse(await readFile(destination,'utf8')), {version:5,vars:{native_test:true}});
    assert.equal(await window.webContents.executeJavaScript("window.vericivilDesktop.access"), 'free');
    assert.equal((await window.webContents.executeJavaScript("window.vericivilDesktop.updateState()")).status, 'disabled');
    await window.webContents.executeJavaScript("window.vericivilDesktop.saveRecovery(JSON.stringify({version:5,vars:{recovery_test:true}}))");
    const recovered = JSON.parse(await readFile(path.join(app.getPath('userData'), 'recovery.json'), 'utf8'));
    assert.equal(recovered.vars.recovery_test, true);
    await window.webContents.executeJavaScript("window.vericivilDesktop.saveRecovery(null)");
    await window.webContents.executeJavaScript("window.vericivilDesktop.newProject()");
    let suggestedProject;
    dialog.showSaveDialog = async (_window, options) => { suggestedProject = options.defaultPath; return { canceled: true }; };
    await window.webContents.executeJavaScript("Array.from(document.querySelectorAll('.desktop-toolbar button')).find(button => button.textContent === 'Save project').click()");
    for (let attempt = 0; attempt < 100 && !suggestedProject; attempt++) await new Promise(resolve => setTimeout(resolve, 20));
    assert.ok(suggestedProject?.endsWith('.' + edition.projectExtension));
  } finally { dialog.showSaveDialog = originalDialog; await rm(folder,{recursive:true,force:true}); }
  const geometry = [];
  for (const [width,height] of [[1040,760],[1440,960]]) {
    window.setSize(width,height,false);
    for (let attempt=0; attempt<200; attempt++) {
      const renderedWidth = await window.webContents.executeJavaScript('innerWidth');
      if (window.getSize()[0] === width && renderedWidth === window.getContentSize()[0]) break;
      await new Promise(resolve => setTimeout(resolve,50));
    }
    assert.equal(window.getSize()[0],width,'requested window width');
    const layout = await window.webContents.executeJavaScript(`(() => {
      const input=document.querySelector('.inputs-panel').getBoundingClientRect();
      const result=document.querySelector('.results-panel').getBoundingClientRect();
      const exports=document.querySelector('.exports').getBoundingClientRect();
      return {width:innerWidth,height:innerHeight,inputRight:input.right,resultLeft:result.left,resultWidth:result.width,exportsBottom:exports.bottom,documentWidth:document.documentElement.scrollWidth};
    })()`);
    assert.equal(layout.width,window.getContentSize()[0],'renderer matches native content width');
    assert.ok(layout.resultLeft >= layout.inputRight);
    assert.ok(layout.resultWidth > 500);
    assert.ok(layout.exportsBottom <= layout.height);
    assert.ok(layout.documentWidth <= layout.width);
    geometry.push(layout);
  }
  for (const theme of ['light','dark']) {
    nativeTheme.themeSource=theme;
    const expectedPaper=theme==='dark'?'#0e1714':'#eef3f1';
    let paper;
    for (let attempt=0; attempt<40; attempt++) {
      paper=await window.webContents.executeJavaScript("getComputedStyle(document.documentElement).getPropertyValue('--paper').trim()");
      if(paper===expectedPaper)break;
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    assert.equal(paper,expectedPaper,`${theme} system appearance`);
    if (process.env.VERICIVIL_CAPTURE_DIR) {
      const { mkdir, writeFile } = require('node:fs/promises');
      await mkdir(process.env.VERICIVIL_CAPTURE_DIR, { recursive: true });
      await new Promise(resolve => setTimeout(resolve, 250));
      await writeFile(path.join(process.env.VERICIVIL_CAPTURE_DIR, `desktop-${theme}.png`), (await window.capturePage()).toPNG());
    }
  }
  nativeTheme.themeSource='system';
  await window.webContents.executeJavaScript("Array.from(document.querySelectorAll('button')).find(button => button.textContent === 'Updates').click()");
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await window.webContents.executeJavaScript("!!document.querySelector('dialog[open]')")) break;
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('dialog[open]')"), true);
  assert.match(await window.webContents.executeJavaScript("document.querySelector('dialog').textContent"), /manual updates/);
  for (const [notes, expected] of [
    ['<p>Code signing policy: <a href="https://vericivil.com/code-signing" rel="nofollow">Signing policy</a>.</p><h2>What\'s Changed</h2><ul><li>Add AASHTO Case II by <a class="user-mention" data-hovercard-url="/users/colewinstead/hovercard" href="https://github.com/colewinstead">@colewinstead</a> in <a href="https://github.com/colewinstead/VeriCivil/pull/85">#85</a></li></ul><p><strong>Full Changelog</strong>: v1.7.4…v1.7.5</p>', 'Code signing policy: Signing policy.\nWhat\'s Changed\n• Add AASHTO Case II by @colewinstead in #85\nFull Changelog: v1.7.4…v1.7.5'],
    ['<p>Fixes &amp; improvements<br>Station &lt; 1000 &mdash; ready &#x2713;</p><ul><li>Save projects</li><li>Export reports</li></ul>', 'Fixes & improvements\nStation < 1000 — ready ✓\n• Save projects\n• Export reports'],
    ['Plain release notes\nSecond line: 1 < 2 & 3 > 2.', 'Plain release notes\nSecond line: 1 < 2 & 3 > 2.'],
    ['<h2>Fixed project saving</h2><ul><li>First fix<li>Second fix</ul>', 'Fixed project saving\n• First fix\n• Second fix'],
    ['<style>body{display:none}</style><script>window.updateNotesExecuted=true</script><p onclick="window.updateNotesExecuted=true">Safe <a href="javascript:window.updateNotesExecuted=true">description</a><img src="https://example.invalid/tracker" onerror="window.updateNotesExecuted=true"></p>', 'Safe description'],
    ['', null],
    ['<script>window.updateNotesExecuted=true</script>', null],
  ]) {
    window.webContents.send('desktop:update', { status: 'available', version: '1.7.5', nextVersion: '1.7.6', notes });
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await window.webContents.executeJavaScript(`(document.querySelector('.update-notes')?.textContent ?? null) === ${JSON.stringify(expected)}`)) break;
      await new Promise(resolve => setTimeout(resolve, 20));
    }
    assert.equal(await window.webContents.executeJavaScript("document.querySelector('.update-notes')?.textContent ?? null"), expected);
    assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('.update-notes a, .update-notes img, .update-notes script, .update-notes style') || !!window.updateNotesExecuted"), false);
    assert.equal(await window.webContents.executeJavaScript("Array.from(document.querySelectorAll('dialog button')).some(button => button.textContent === 'Download update')"), true);
    if (expected?.startsWith('Code signing policy:') && process.env.VERICIVIL_CAPTURE_DIR) {
      const { mkdir, writeFile } = require('node:fs/promises');
      await mkdir(process.env.VERICIVIL_CAPTURE_DIR, { recursive: true });
      await window.webContents.executeJavaScript("document.querySelector('dialog details').open = true");
      for (const theme of ['light', 'dark']) {
        nativeTheme.themeSource = theme;
        await new Promise(resolve => setTimeout(resolve, 250));
        await writeFile(path.join(process.env.VERICIVIL_CAPTURE_DIR, `desktop-update-${theme}.png`), (await window.capturePage()).toPNG());
      }
      nativeTheme.themeSource = 'system';
    }
  }
  console.log('PASS: update descriptions show readable text, decoded entities and separate list items without inserting remote HTML.');
  await window.webContents.executeJavaScript("Array.from(document.querySelectorAll('dialog button')).find(button => button.textContent === 'Close').click()");
  assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('dialog[open]')"), false);
  for (const status of ['current', 'available', 'manual', 'downloaded', 'disabled']) {
    const visible = ['available', 'manual', 'downloaded'].includes(status);
    window.webContents.send('desktop:update', { status, version: '1.9.0', nextVersion: visible ? '1.9.1' : '' });
    for (let attempt = 0; attempt < 100; attempt++) {
      if (await window.webContents.executeJavaScript(`!!document.querySelector('.desktop-update-notice') === ${visible}`)) break;
      await new Promise(resolve => setTimeout(resolve, 20));
    }
    assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('.desktop-update-notice')"), visible, status);
    assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('.desktop-toolbar .desktop-update-highlight')"), visible, status);
    assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('dialog[open]')"), false, 'Update notice does not interrupt work');
    if (!visible) continue;
    assert.match(await window.webContents.executeJavaScript("document.querySelector('.desktop-update-notice [role=status]').textContent"), /1\.9\.1/);
    if (status === 'available' && process.env.VERICIVIL_CAPTURE_DIR) {
      const { mkdir, writeFile } = require('node:fs/promises');
      await mkdir(process.env.VERICIVIL_CAPTURE_DIR, { recursive: true });
      for (const theme of ['light', 'dark']) {
        nativeTheme.themeSource = theme;
        await new Promise(resolve => setTimeout(resolve, 250));
        await writeFile(path.join(process.env.VERICIVIL_CAPTURE_DIR, `desktop-update-notice-${theme}.png`), (await window.capturePage()).toPNG());
      }
      nativeTheme.themeSource = 'system';
    }
    await window.webContents.executeJavaScript("document.querySelector('.desktop-update-notice button').click()");
    assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('dialog[open]')"), true, 'Review update opens existing dialog');
    await window.webContents.executeJavaScript("Array.from(document.querySelectorAll('dialog button')).find(button => button.textContent === 'Close').click()");
  }
  console.log('PASS: desktop update notice and toolbar highlight persist for available/manual/downloaded updates; review opens the dialog without forcing it.');
  await window.webContents.executeJavaScript(`(() => {
    window.confirm = () => true;
    const original = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function(...args) { window.testWorker = this; return original.apply(this, args); };
    window.restoreWorkerPrototype = () => { Worker.prototype.postMessage = original; };
    Array.from(document.querySelectorAll('button')).find(button => button.textContent === 'Load synthetic sample').click();
  })()`);
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await window.webContents.executeJavaScript('!!window.testWorker')) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert.equal(await window.webContents.executeJavaScript('!!window.testWorker'), true);
  await window.webContents.executeJavaScript("window.restoreWorkerPrototype(); window.testWorker.dispatchEvent(new ErrorEvent('error', {message:'Synthetic worker failure'}))");
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await window.webContents.executeJavaScript("!!document.querySelector('.runtime-gate button')")) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert.equal(await window.webContents.executeJavaScript("Array.from(document.querySelectorAll('input')).some(input => input.value === 'Synthetic free sample')"), true);
  await window.webContents.executeJavaScript("document.querySelector('.runtime-gate button').click()");
  for (let attempt = 0; attempt < 600; attempt++) {
    if (await window.webContents.executeJavaScript("!!document.querySelector('.desktop-runtime.ready')")) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert.equal(await window.webContents.executeJavaScript("!!document.querySelector('.desktop-runtime.ready')"), true);
  assert.equal(await window.webContents.executeJavaScript("Array.from(document.querySelectorAll('input')).some(input => input.value === 'Synthetic free sample')"), true);
  console.log('PASS: worker failure offers retry and retains the project inputs.');
  console.log('PASS: native save bridge writes and cancels correctly; laptop/wide layout:',JSON.stringify(geometry));
  console.log('PASS: actual offline Electron worker matches native Python; LandXML, project roundtrip, PDF, ORD CSV and overlay DXF passed; remote requests blocked and renderer isolated.');
  clearTimeout(timer);app.exit(0);
}).catch(error => { console.error(error); clearTimeout(timer);app.exit(1); });
