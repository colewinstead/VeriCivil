const assert = require('node:assert/strict');
const { spawn, spawnSync, execFileSync } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');

async function verify() {
  if (process.env.GITHUB_ACTIONS !== 'true' || process.platform !== 'win32') throw new Error('Run installed acceptance on the disposable Windows CI runner.');
  const executable = process.argv[2];
  if (!executable || !path.resolve(executable).toLowerCase().startsWith(path.resolve(process.env.RUNNER_TEMP) .toLowerCase() + path.sep)) throw new Error('Installed app must be inside RUNNER_TEMP.');
  const reservation = net.createServer();
  await new Promise(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const port = reservation.address().port;
  await new Promise(resolve => reservation.close(resolve));
  const application = spawn(executable, [`--remote-debugging-port=${port}`, '--remote-debugging-address=127.0.0.1'], { windowsHide: true, stdio: 'ignore' });
  const started = new Promise((resolve, reject) => { application.once('spawn', resolve); application.once('error', reject); });
  let socket, timer;
  const requests = new Map();
  const inputs = { pc: '10+00', pt: '12+00', speed: '45', radius: '1200', facility: 'centerline', area: 'rural', lane_width: '12', lanes_rotated: '2', normal_crown: '0.02', curve_direction: 'right' };
  const entitlement = { plan: 'pro', status: 'active' };
  try {
    await started;
    await Promise.race([new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Installed runtime acceptance timed out.')), 120000); }), (async () => {
      let page;
      for (let attempt = 0; attempt < 300; attempt++) {
        try {
          const response = await fetch(`http://127.0.0.1:${port}/json/list`, { signal: AbortSignal.timeout(1000) });
          page = (await response.json()).find(target => target.type === 'page' && target.url.startsWith('vericivil://app/'));
          if (page) break;
        } catch { /* The installed app may still be starting. */ }
        if (application.exitCode !== null) throw new Error('Installed app exited before opening its workspace.');
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      if (!page) throw new Error('Installed workspace did not open.');
      socket = new WebSocket(page.webSocketDebuggerUrl);
      await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', () => reject(new Error('Could not connect to the installed workspace.')), { once: true }); });
      socket.addEventListener('message', event => {
        const message = JSON.parse(event.data);
        const pending = requests.get(message.id);
        if (!pending) return;
        requests.delete(message.id);
        if (message.error) pending.reject(new Error(message.error.message)); else pending.resolve(message.result);
      });
      socket.addEventListener('close', () => { requests.forEach(({ reject }) => reject(new Error('Installed workspace closed.'))); requests.clear(); });
      const result = await new Promise((resolve, reject) => {
        requests.set(1, { resolve, reject });
        socket.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { awaitPromise: true, returnByValue: true, expression: `(async () => {
          const worker = new Worker('/pyodide-worker.js');
          try {
            await new Promise((resolve, reject) => {
              worker.onmessage = ({data}) => { if(data.type==='ready')resolve(); if(data.type==='fatal')reject(new Error(data.message)); };
              worker.onerror = () => reject(new Error('Installed worker could not start.'));
              worker.postMessage({operation:'initialize'});
            });
            const calculation = await new Promise((resolve, reject) => {
              worker.onmessage = ({data}) => { if(data.type==='response') { if(data.ok)resolve(data.result); else reject(new Error(data.error?.message)); } };
              worker.postMessage({id:1,operation:'calculate',payload:${JSON.stringify({inputs,entitlement})}});
            });
            return {calculation:JSON.stringify(calculation,(_key,value)=>value===undefined?null:value), require:typeof window.require, node:typeof window.process};
          } finally { worker.terminate(); }
        })()` } }));
      });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || 'Installed worker failed.');
      const actual = result.result.value;
      const expected = JSON.parse(execFileSync('python', ['-c', 'import sys,json,super_service; print(json.dumps(super_service.dispatch("calculate",sys.stdin.read())))'], { cwd: path.resolve(__dirname, '../..'), input: JSON.stringify({ inputs, entitlement }), encoding: 'utf8' }));
      assert.deepEqual(JSON.parse(actual.calculation), expected);
      assert.equal(actual.require, 'undefined');
      assert.equal(actual.node, 'undefined');
      console.log('PASS: installed executable loads its bundled offline engine, matches native Python, and isolates renderer Node access.');
    })()]);
  } finally {
    clearTimeout(timer);
    socket?.close();
    if (application.pid) spawnSync('taskkill', ['/PID', String(application.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
  }
}
verify().catch(error => { console.error(error.message); process.exitCode = 1; });
