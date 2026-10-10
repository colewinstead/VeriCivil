import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const launcher = fileURLToPath(new URL("../build/prepare-python-runtime.mjs", import.meta.url));

test("stages the authoritative runtime even when launched outside the web directory", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "vericivil-runtime-"));
  try {
    const result = spawnSync(process.execPath, [launcher], { cwd, encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /Staged \d+ shared Python modules/);
    const source = await readFile(new URL("../../app_info.py", import.meta.url), "utf8");
    const staged = await readFile(new URL("../public/python/app_info.py", import.meta.url), "utf8");
    assert.equal(staged, source);
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("a missing interpreter fails with an actionable message", () => {
  const result = spawnSync(process.execPath, [launcher], {
    env: { ...process.env, PATH: "" },
    encoding: "utf8",
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unable to run python3?\. Install Python 3\.11\+/);
});
