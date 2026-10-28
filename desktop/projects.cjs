const fs = require('node:fs/promises');
const path = require('node:path');
const { saveAtomically } = require('./files.cjs');

const MAX_PROJECT_BYTES = 64 * 1024 * 1024;
function projectContent(content) {
  if (typeof content !== 'string' || Buffer.byteLength(content) > MAX_PROJECT_BYTES) throw new Error('Project exceeds 64 MiB.');
  const project = JSON.parse(content);
  if (!project || typeof project !== 'object' || Array.isArray(project) || !Number.isInteger(project.version) || !project.vars || typeof project.vars !== 'object' || Array.isArray(project.vars)) throw new Error('Select a valid saved VeriCivil project.');
  return content;
}

class Projects {
  constructor(directory) {
    this.directory = directory;
    this.recent = [];
    this.queue = Promise.resolve();
  }
  async initialize() {
    await fs.mkdir(this.directory, { recursive: true, mode: 0o700 });
    try {
      const recent = JSON.parse(await fs.readFile(path.join(this.directory, 'recent.json'), 'utf8'));
      if (Array.isArray(recent)) this.recent = recent.filter(item => typeof item === 'string' && path.isAbsolute(item)).slice(0, 10);
    } catch (error) { if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error; }
  }
  async remember(file) {
    this.recent = [file, ...this.recent.filter(item => item !== file)].slice(0, 10);
    await saveAtomically(path.join(this.directory, 'recent.json'), JSON.stringify(this.recent));
  }
  async read(file) {
    if (!path.isAbsolute(file) || !['.json', '.vericivil'].includes(path.extname(file).toLowerCase())) throw new Error('Select a saved VeriCivil project.');
    const stat = await fs.stat(file);
    if (!stat.isFile() || stat.size > MAX_PROJECT_BYTES) throw new Error('Project exceeds 64 MiB or is not a file.');
    const content = projectContent(await fs.readFile(file, 'utf8'));
    return { name: path.basename(file), content };
  }
  async recovery() {
    await this.queue;
    try { return await this.read(path.join(this.directory, 'recovery.json')); }
    catch (error) { if (error.code === 'ENOENT') return null; throw error; }
  }
  saveRecovery(content) {
    if (content !== null) projectContent(content);
    const operation = this.queue.catch(() => {}).then(async () => {
      const file = path.join(this.directory, 'recovery.json');
      if (content === null) await fs.rm(file, { force: true });
      else await saveAtomically(file, content);
    });
    this.queue = operation;
    return operation;
  }
}
module.exports = { Projects, projectContent, MAX_PROJECT_BYTES };
