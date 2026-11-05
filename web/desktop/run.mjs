import electron from 'electron';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import editionTools from '../../desktop/edition.cjs';

const edition = editionTools.getEdition();
const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;
const result = spawnSync(electron, [fileURLToPath(new URL(`../../desktop/${edition.appDirectory}/`, import.meta.url))], { stdio: 'inherit', env });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
