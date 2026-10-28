const { writeFile, rename, rm } = require('node:fs/promises');
const { randomUUID } = require('node:crypto');
const path = require('node:path');

async function saveAtomically(destination, bytes) {
  const temporary = path.join(path.dirname(destination), `.vericivil-${randomUUID()}.tmp`);
  try {
    await writeFile(temporary, bytes, { flag: 'wx', mode: 0o600 });
    await rename(temporary, destination);
  } finally {
    await rm(temporary, { force: true }).catch(() => {});
  }
}
module.exports = { saveAtomically };
