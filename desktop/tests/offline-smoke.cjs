const { app, dialog, nativeTheme } = require('electron');
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
const original = require('../app/main.cjs');
original.start().then(async (window) => {
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
    worker.terminate();
    let remoteBlocked=false;try{await fetch('https://vericivil.com/')}catch{remoteBlocked=true}
    return {manifest,calculation,csv:csv.content,pdf:pdf.content.slice(0,4),dxf:Array.from(dxf.content).slice(0,200),loaded,remoteBlocked,
      rendererSecurity:{require:typeof window.require,node:typeof window.process},
      ui:document.querySelector('main')?.className};
  })()`);
  const python = process.platform === 'win32' ? 'python' : 'python3';
  const expected = JSON.parse(execFileSync(python, ['-c', 'import sys,json,super_service; print(json.dumps(super_service.dispatch("calculate",sys.stdin.read())))'], { cwd:root, input: JSON.stringify({inputs,entitlement:{plan:'pro',status:'active'}}), encoding:'utf8' }));
  // Pyodide maps Python None to undefined; native JSON represents it as null.
  assert.deepEqual(JSON.parse(JSON.stringify(result.calculation, (_key, value) => value === undefined ? null : value)), expected);
  assert.match(result.csv,/SuperelevationLane,Station,CrossSlope/);
  assert.equal(String.fromCharCode(...result.pdf),'%PDF');
  assert.match(Buffer.from(result.dxf).toString(),/SECTION/);
  assert.deepEqual(JSON.parse(JSON.stringify(result.loaded.project.last_results)), JSON.parse(JSON.stringify(result.calculation.results)));
  assert.equal(result.remoteBlocked,true);
  assert.deepEqual(result.rendererSecurity,{require:'undefined',node:'undefined'});
  assert.match(result.ui,/desktop-workspace/);
  const folder = await mkdtemp(path.join(tmpdir(), 'vericivil-native-dialog-'));
  const originalDialog = dialog.showSaveDialog;
  try {
    dialog.showSaveDialog = async () => ({ canceled: true });
    assert.equal(await window.webContents.executeJavaScript("window.vericivilDesktop.saveFile('project.json',new TextEncoder().encode('native test'))"), 'cancelled');
    assert.deepEqual(await readdir(folder), []);
    const destination = path.join(folder, 'project.json');
    dialog.showSaveDialog = async () => ({ canceled: false, filePath: destination });
    assert.equal(await window.webContents.executeJavaScript("window.vericivilDesktop.saveFile('project.json',new TextEncoder().encode('native test'))"), 'saved');
    assert.equal(await readFile(destination,'utf8'),'native test');
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
  }
  nativeTheme.themeSource='system';
  console.log('PASS: native save bridge writes and cancels correctly; laptop/wide layout:',JSON.stringify(geometry));
  console.log('PASS: actual offline Electron worker matches native Python; LandXML, project roundtrip, PDF, ORD CSV and overlay DXF passed; remote requests blocked and renderer isolated.');
  clearTimeout(timer);app.exit(0);
}).catch(error => { console.error(error); clearTimeout(timer);app.exit(1); });
