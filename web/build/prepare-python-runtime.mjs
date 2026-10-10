import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// npm does not inherit interactive shell aliases such as `python=python3`.
const python = process.platform === "win32" ? "python" : "python3";
const script = fileURLToPath(new URL("../../scripts/prepare_web_runtime.py", import.meta.url));
const result = spawnSync(python, [script], { stdio: "inherit" });

if (result.error) {
  console.error(`Unable to run ${python}. Install Python 3.11+ and make sure ${python} is on PATH.`);
}
process.exit(result.status ?? 1);
