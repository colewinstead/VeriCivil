const assert = require('node:assert/strict');
const { app, BrowserWindow, dialog, nativeTheme } = require('electron');
const { mkdtempSync, writeFileSync, readFileSync, mkdirSync, rmSync } = require('node:fs');
const { execFileSync } = require('node:child_process');
const { tmpdir } = require('node:os');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const { application_version: applicationVersion } = JSON.parse(readFileSync(path.join(root, 'web/app/generated/release-info.json'), 'utf8'));
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
}) : require(path.join(__dirname, '..', require('../edition.cjs').getEdition().appDirectory, 'main.cjs')).start();
launch.then(async window => {
  window.webContents.setBackgroundThrottling(false);
  window.webContents.on("console-message", event => { if (event.level === "error") console.error("Renderer:", event.message); });
  const js = code => window.webContents.executeJavaScript(code);
  const wait = async code => {
    for (let attempt = 0; attempt < 250; attempt++) {
      if (await js(code)) return;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    console.error(await js("document.querySelector('.cross-section-view')?.outerHTML.slice(0,2500) || document.body.innerText.slice(-1200)"));
    if (capture) writeFileSync(path.join(capture, "smoke-failure.png"), (await window.capturePage()).toPNG());
    console.error(await js('JSON.stringify({requests:window.sectionRequests,input:document.querySelector(".cross-section-station input")?.value,active:document.activeElement?.tagName})'));
    throw new Error(`Timed out: ${code}`);
  };
  await wait(browserUrl ? `document.querySelector('.privacy-strip .version')?.textContent.includes(${JSON.stringify(applicationVersion)})` : "!!document.querySelector('.desktop-runtime.ready')");
  const python = process.platform === 'win32' ? 'python' : 'python3';
  const fixture = JSON.parse(execFileSync(python, ['-c', `
import json, super_service
values = {"criteria_profile":"aashto-green-book-2018-2019-10","project_name":"Synthetic cross-section acceptance","pc":"1000","pt":"2000","speed":"60","radius":"2000","e_manual":"0.06","area":"rural","runoff_tangent_percent":"70","normal_crown":"0.02","lane_widths":"12,12,12,12","rotation_axis":"centerline","curve_direction":"left"}
result = super_service.calculate_curve(values)["results"]
ramp_values = {**values,"pc":"5000","pt":"6000","roadway":"one_way","initial_section":"single_slope","initial_slope":"0.02","lane_widths":"11,11,11","rotation_axis":"right_edge","curve_direction":"right"}
ramp = super_service.calculate_curve(ramp_values)["results"]
case_values={**values,"roadway":"divided_case_ii","pc":"7000","pt":"9000","case_ii":{side:{"speed":65,"radius":3000,"lane_count":4,"lane_width":12,"pivot_offset":offset,"initial_slope":slope,"runoff_tangent_percent":70} for side,offset,slope in [("left",-20,-.02),("right",20,.02)]}}
case_result=super_service.calculate_curve(case_values)["results"]
curves = [{"results":result,"meta":{"curve_direction":"left","curve_name":"Synthetic four-lane undivided"}}, {"results":ramp,"meta":{"curve_direction":"right","curve_name":"Synthetic three-lane ramp"}}, {"results":case_result,"meta":{"curve_direction":"left","curve_name":"Synthetic Case II"}}]
content = super_service.project_save({"version":5,"vars":values,"curves":curves,"last_results":result,"last_meta":curves[0]["meta"]})
case_stops=super_service.corridor_diagram(curves)["curves"][2]["snap_points"]
case_index=next(index for index,stop in enumerate(case_stops) if "Full super" in stop["labels"] and stop["lanes"]==["left"])
print(json.dumps({"content":content,"full":result["full_super_ft"],"preview_start":result["zero_crown_ft"],"results":result,"case_previous":case_stops[case_index-1],"case_full":case_stops[case_index]}))
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
  await js(`window.sectionRequests=[]; window.sectionDelay=0; window.sectionIds=new Set();
    var sectionPost=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(message,...args){
      if(message.operation==='diagram_lookup') {
        window.sectionRequests.push(message.payload.station); window.sectionIds.add(message.id);
        if(!this.sectionWrapped) {
          this.sectionWrapped=true; const receive=this.onmessage;
          this.onmessage=event=>{
            if(window.sectionIds.delete(event.data.id) && window.sectionDelay) setTimeout(()=>receive.call(this,event),window.sectionDelay);
            else receive.call(this,event);
          };
        }
      }
      return sectionPost.call(this,message,...args);
    }; undefined;`);
  const before = await station();
  await js("document.querySelector('[aria-label=\"Cross-section station scrubber\"]').focus()");
  window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Right' });
  window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Right' });
  await wait(`Number(document.querySelector('[aria-label="Cross-section station scrubber"]').value)===${before + 1} && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'`);
  assert.equal(await js("document.querySelector('.cross-section-event').textContent"),'Between stopping points');
  const enter = async text => {
    window.focus();
    window.webContents.focus();
    await js("var input=document.querySelector('[aria-label=\"Cross-section station\"]'); input.focus(); input.select();");
    window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Backspace' });
    window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Backspace' });
    await wait("document.querySelector('[aria-label=\"Cross-section station\"]').value===''");
    for (const character of text) window.webContents.sendInputEvent({ type: 'char', keyCode: character });
    await wait(`document.querySelector('[aria-label="Cross-section station"]').value===${JSON.stringify(text)}`);
    await js('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
    await js("document.querySelector('.cross-section-station button').click()");
  };
  await enter(String(fixture.preview_start));
  await wait(`Number(document.querySelector('[aria-label="Cross-section station scrubber"]').value)===${fixture.preview_start} && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'`);
  await js(`window.sectionDelay=450; window.sectionRequests=[]; window.sectionFrames=[]; window.sectionRecording=true;
    window.sectionSvg=document.querySelector('.cross-section-drawing svg');
    function recordSection(){
      const slider=document.querySelector('[aria-label="Cross-section station scrubber"]');
      const drawing=document.querySelector('.cross-section-drawing'); const view=document.querySelector('.cross-section-view');
      window.sectionFrames.push({station:Number(slider.value),label:document.querySelector('.cross-section-readout strong').textContent,accessibleLabel:slider.getAttribute('aria-valuetext'),top:slider.getBoundingClientRect().top,
        height:drawing.getBoundingClientRect().height,scroll:view.scrollTop,page:window.scrollY,
        caption:document.querySelector('.cross-section-event').textContent,scrubbing:document.querySelector('.cross-section-event').classList.contains('scrubbing'),captionHeight:document.querySelector('.cross-section-event').getBoundingClientRect().height,
        mounted:window.sectionSvg===drawing.querySelector('svg'),table:!!document.querySelector('.cross-section-table'),
        slopes:Array.from(drawing.querySelectorAll('.section-slope'),item=>item.textContent),
        mobile:Array.from(document.querySelectorAll('.cross-section-mobile-labels strong'),item=>item.textContent),
        edges:Array.from(drawing.querySelectorAll('.section-segment line'),item=>Number(item.getAttribute('y1')))});
      if(window.sectionRecording)requestAnimationFrame(recordSection);
    } requestAnimationFrame(recordSection);`);
  const track = await js(`(() => {const input=document.querySelector('[aria-label="Cross-section station scrubber"]'); const rect=input.getBoundingClientRect(); return {left:rect.left+8,width:rect.width-16,y:rect.top+rect.height/2,min:Number(input.min),max:Number(input.max)};})()`);
  const point = fraction => ({ x: Math.round(track.left + ((fixture.preview_start + fraction * (fixture.full - fixture.preview_start) - track.min) / (track.max - track.min)) * track.width), y: Math.round(track.y) });
  window.webContents.sendInputEvent({ type: 'mouseMove', ...point(0) });
  window.webContents.sendInputEvent({ type: 'mouseDown', button: 'left', clickCount: 1, ...point(0) });
  const motion = [...Array.from({length: 12}, (_,i)=>(i+1)/15), ...Array.from({length: 12}, (_,i)=>.8-(i+1)/24)];
  for (let index=0; index<motion.length; index++) {
    window.webContents.sendInputEvent({ type: 'mouseMove', modifiers: ['leftbuttondown'], ...point(motion[index]) });
    await new Promise(resolve=>setTimeout(resolve,index===6?140:24));
    if (capture && index===12) writeFileSync(path.join(capture,`cross-section-preview-${browserUrl?'browser':'electron'}.png`),(await window.capturePage()).toPNG());
  }
  window.webContents.sendInputEvent({ type: 'mouseUp', button: 'left', clickCount: 1, ...point(motion.at(-1)) });
  const stopped = await station();
  await wait(`Number(document.querySelector('[aria-label="Cross-section station scrubber"]').value)===${stopped} && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'`);
  const samples = await js('window.sectionRecording=false; window.sectionDelay=0; window.sectionFrames');
  const previews = samples.filter(sample=>sample.slopes.some(label=>label.startsWith('≈')));
  assert.ok(previews.length>5, 'native sustained dragging shows continuous previews while responses are delayed');
  assert.ok(new Set(previews.map(sample=>JSON.stringify(sample.slopes))).size>5, 'live percentages change throughout the drag');
  assert.ok(new Set(previews.map(sample=>JSON.stringify(sample.edges))).size>5, 'geometry moves with live percentages');
  const scrubbingSamples=samples.filter(sample=>sample.scrubbing);
  assert.ok(scrubbingSamples.length>5,'the test records a sustained drag');
  assert.deepEqual([...new Set(scrubbingSamples.map(sample=>sample.caption))],['Scrubbing…'],'event captions stay quiet throughout the gesture, including pauses');
  assert.notEqual(await js("document.querySelector('.cross-section-event').textContent"),'Scrubbing…','the caption settles after release');
  const expectedPreviews = JSON.parse(execFileSync(python,['-c','import json,sys,super_service; data=json.load(sys.stdin); print(json.dumps([super_service.diagram_lookup(data["results"],"left",station) for station in data["stations"]]))'],{cwd:root,input:JSON.stringify({results:fixture.results,stations:previews.map(sample=>sample.station)}),encoding:'utf8'}));
  previews.forEach((sample,index)=>{
    const packet=expectedPreviews[index]; const bounds=packet.cross_section.bounds;
    assert.equal(sample.label,packet.station,'station notation stays visible while scrubbing');
    assert.equal(sample.accessibleLabel,sample.label,'the slider announces the same formatted station');
    packet.cross_section.segments.forEach((segment,lane)=>{
      const slope=packet.lanes[segment.name].slope_pct;
      assert.ok(Math.abs(Number.parseFloat(sample.slopes[lane].replace('≈',''))-slope)<=.00501,'preview percentage follows the current station');
      assert.ok(Math.abs(sample.edges[lane]-(210-segment.left.y*760/(bounds.x_max-bounds.x_min)*5))<1e-8,'preview geometry follows the same station as its percentage');
    });
  });
  for (const sample of samples) {
    assert.equal(sample.mounted,true,'the SVG stays mounted');
    assert.equal(sample.table,true,'the exact table stays mounted');
    assert.deepEqual(sample.mobile,sample.slopes,'mobile percentages match the SVG');
    for (const key of ['top','height','scroll','page','captionHeight']) assert.ok(Math.abs(sample[key]-samples[0][key])<1,`${key} stays stable during scrubbing`);
  }
  const exact = JSON.parse(execFileSync(python,['-c','import json,sys,super_service; print(json.dumps(super_service.diagram_lookup(json.loads(sys.stdin.read()),"left",float(sys.argv[1]))))',String(stopped)],{cwd:root,input:JSON.stringify(fixture.results),encoding:'utf8'}));
  assert.deepEqual(await js("Array.from(document.querySelectorAll('.section-slope'),item=>item.textContent)"),exact.cross_section.segments.map(segment=>segment.slope_label));
  assert.ok((await js("document.querySelector('.cross-section-table caption').textContent")).includes(`Exact at ${exact.station}`));
  assert.equal(await js('window.sectionRequests.at(-1)'),stopped,'release requests the final exact station');
  assert.ok(await js('window.sectionRequests.length')<motion.length,'exact requests are coalesced during dragging');
  console.log('PASS: sustained native drag, live percentages, stable layout, reversal, delayed responses and exact settlement.');
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
  await wait("!!document.querySelector('.cross-section-error[role=alert]')");
  assert.match(await js("document.querySelector('.cross-section-error').textContent"), /within this curve/);
  await js("document.querySelector('[aria-label=\"Previous section event\"]').click()");
  await wait("!document.querySelector('.cross-section-error[role=alert]') && document.querySelectorAll('.cross-section-drawing .section-segment').length===4");
  const beforeWheel = await station();
  await js("var slider=document.querySelector('[aria-label=\"Cross-section station scrubber\"]'); slider.focus(); slider.dispatchEvent(new WheelEvent('wheel',{deltaY:10,bubbles:true,cancelable:true}));");
  await wait(`Number(document.querySelector('[aria-label="Cross-section station scrubber"]').value)===${beforeWheel + 1} && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'`);
  await js("window.sectionRequests=[]; document.querySelector('[aria-label=\"Cross-section station scrubber\"]').dispatchEvent(new WheelEvent('wheel',{deltaY:10,bubbles:true,cancelable:true})); var curve=document.querySelector('[aria-label=\"Cross-section curve\"]'); curve.value='1'; curve.dispatchEvent(new Event('change',{bubbles:true}));");
  await wait("document.querySelectorAll('.cross-section-drawing .section-segment').length===3 && document.querySelector('.cross-section-heading h4').textContent==='One-way / ramp' && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'");
  assert.ok(await station() > 4000, 'switching curves clamps station into its own domain instead of bridging the gap');
  assert.equal(await js(`window.sectionRequests.includes(${beforeWheel+2})`),false,'switching curves cancels the prior curve\'s debounced lookup');
  await js("var curve=document.querySelector('[aria-label=\"Cross-section curve\"]'); curve.value='0'; curve.dispatchEvent(new Event('change',{bubbles:true}));");
  await wait("document.querySelectorAll('.cross-section-drawing .section-segment').length===4 && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'");
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
  window.setSize(1440, 960);
  await js("document.querySelectorAll('.curve-list-item > button')[2].click()");
  await wait("document.querySelectorAll('.case-ii-side').length===2 && document.querySelectorAll('.case-ii-results section').length===2");
  assert.equal(await js('document.querySelector(\'[aria-label="left carriageway Pivot baseline offset (ft)"]\').value'), '-20');
  assert.equal(await js('document.querySelector(\'[aria-label="right carriageway Pivot baseline offset (ft)"]\').value'), '20');
  assert.equal(await js("Array.from(document.querySelectorAll('.case-ii-side input')).every(input=>input.getBoundingClientRect().height<100)"), true, 'offset guidance does not stretch input rows');
  if (capture) {
    for (const theme of ['light', 'dark']) {
      nativeTheme.themeSource = theme;
      await js("document.querySelector('.case-ii-inputs').scrollIntoView({block:'start'})");
      await new Promise(resolve=>setTimeout(resolve,100));
      writeFileSync(path.join(capture, `case-ii-inputs-${browserUrl ? 'browser' : 'electron'}-${theme}.png`), (await window.capturePage()).toPNG());
    }
  }
  assert.match(await js("document.querySelector('[aria-label=\"left carriageway results\"]').textContent"), /216.00/);
  assert.match(await js("document.querySelector('[aria-label=\"right carriageway results\"]').textContent"), /336.00/);
  await js("Array.from(document.querySelectorAll('[role=tab]')).find(button=>button.textContent==='Cross Section').click()");
  await js("var curve=document.querySelector('[aria-label=\"Cross-section curve\"]'); curve.value='2'; curve.dispatchEvent(new Event('change',{bubbles:true}));");
  await wait("document.querySelectorAll('.cross-section-drawing .section-segment').length===8 && document.querySelectorAll('.section-pivot').length===2 && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'");
  assert.match(await js("document.querySelector('.section-median-gap').textContent"), /40.0 ft/);
  await enter(String(fixture.case_previous.station_ft));
  await wait(`document.querySelector('.cross-section-readout strong').textContent===${JSON.stringify(fixture.case_previous.station)} && document.querySelector('.cross-section-drawing').getAttribute('aria-busy')==='false'`);
  assert.ok((await js("document.querySelector('[aria-label=\"Next section event\"]').title")).includes('Full superelevation · Left lanes'));
  await js("document.querySelector('[aria-label=\"Next section event\"]').click()");
  await wait(`document.querySelector('.cross-section-readout strong').textContent===${JSON.stringify(fixture.case_full.station)} && document.querySelector('.cross-section-event').textContent==='Full superelevation · Left lanes'`);
  if (!window.webContents.debugger.isAttached()) window.webContents.debugger.attach('1.3');
  await window.webContents.debugger.sendCommand('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  assert.equal(await js("getComputedStyle(document.querySelector('.cross-section-event')).transitionDuration"),'0s');
  await window.webContents.debugger.sendCommand('Emulation.setEmulatedMedia',{features:[]});
  await enter('7300');
  await wait("document.querySelector('.cross-section-readout strong').textContent==='73+00.000'");
  await js("document.querySelector('.expand-analysis').click()");
  for (const theme of browserUrl ? ['desktop', 'mobile'] : ['light', 'dark']) {
    if (!browserUrl) nativeTheme.themeSource = theme;
    window.setSize(theme === 'mobile' ? 414 : 1440, theme === 'mobile' ? 896 : 960);
    await new Promise(resolve=>setTimeout(resolve,200));
    assert.equal(await js('document.documentElement.scrollWidth<=innerWidth'), true, 'Case II fits viewport');
    if (capture) writeFileSync(path.join(capture, `case-ii-${browserUrl ? 'browser' : 'electron'}-${theme}.png`), (await window.capturePage()).toPNG());
  }
  window.setSize(1440, 960);
  await js("document.querySelector('.expand-analysis').click()");
  await js("var radius=document.querySelector('[aria-label=\"left carriageway Design radius (ft)\"]'); radius.focus(); radius.select();");
  window.webContents.sendInputEvent({type:'keyDown',keyCode:'Backspace'});
  window.webContents.sendInputEvent({type:'keyUp',keyCode:'Backspace'});
  for (const character of '4000') window.webContents.sendInputEvent({type:'char',keyCode:character});
  await wait("document.querySelector('[aria-label=\"left carriageway results\"]')?.textContent.includes('144.00')");
  assert.match(await js("document.querySelector('[aria-label=\"right carriageway results\"]').textContent"), /336.00/);
  console.log('Case II: paired native inputs, independent recomputation, eight lanes, level pivots and median interval passed.');
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
