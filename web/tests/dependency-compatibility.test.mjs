import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { fileURLToPath } from "node:url";
import test from "node:test";
import React from "react";
import { ImageResponse } from "@vercel/og";
import { imageSize } from "image-size";

const require = createRequire(import.meta.url);

test("patched image dependencies preserve OG PNG rendering and dimension reads", async () => {
  const response = new ImageResponse(React.createElement("div", {
    style: { display: "flex", fontSize: 32, color: "black", background: "white" },
  }, "<VeriCivil> & lanes"), { width: 400, height: 100 });
  const png = Buffer.from(await response.arrayBuffer());
  assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  assert.deepEqual(imageSize(png), { width: 400, height: 100, type: "png" });
});

test("the legacy schema loader still transforms TypeScript with patched esbuild", async () => {
  const { transform, transformSync } = require("@esbuild-kit/core-utils");
  const source = "const value: number = 42; export default value;";
  const sourcePath = fileURLToPath(new URL("../db/schema.ts", import.meta.url));
  for (const output of [transformSync(source, sourcePath, { format: "cjs" }),
    await transform(source, sourcePath, { format: "cjs" })]) {
    const compiledModule = { exports: {} };
    runInNewContext(output.code, { module: compiledModule, exports: compiledModule.exports });
    assert.equal(compiledModule.exports.default, 42);
  }
});
