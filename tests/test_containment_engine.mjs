import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { analyze, parseJSON } from "../docs/containment-engine.js";
import fs from "node:fs";
const py = process.env.PYTHON ?? "python";
test("containment complete reports: twelve controls and100 seeded requests", () => {
  const p = spawnSync(
    py,
    [
      "-c",
      "import json;from provlab.containment import analyze;from tools.containment_cases import controls,requests;print(json.dumps([{'input':r,'report':analyze(r)}for r in [c['input']for c in controls()]+requests(100)]))",
    ],
    { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
  );
  assert.equal(p.status, 0, p.stderr);
  const cases = JSON.parse(p.stdout);
  for (const c of cases) assert.deepEqual(analyze(c.input), c.report);
  console.log(
    JSON.stringify({
      containment_reports: cases.length,
      candidate_mappings: cases.reduce(
        (n, c) =>
          n + c.report.directions.reduce((m, d) => m + d.candidates.length, 0),
        0,
      ),
      subset_rows: cases.reduce(
        (n, c) =>
          n +
          c.report.minimization.left.atlas.length +
          c.report.minimization.right.atlas.length,
        0,
      ),
    }),
  );
});
test("containment parser and prototype names", () => {
  const control = JSON.parse(
    fs.readFileSync(
      new URL("../docs/containment-controls.json", import.meta.url),
    ),
  )[0].input;
  for (const raw of ['{"a":1,"a":2}', '{"a":NaN}', "{} extra"])
    assert.throws(() => parseJSON(raw));
  for (const name of [
    "constructor",
    "__proto__",
    "hasOwnProperty",
    "toString",
  ]) {
    const r = {
      schema: [{ name: "constructor", arity: 1 }],
      left: {
        head: [name],
        body: [{ relation: "constructor", terms: [{ var: name }] }],
      },
      right: {
        head: ["y"],
        body: [{ relation: "constructor", terms: [{ var: "y" }] }],
      },
    };
    const p = spawnSync(
      py,
      [
        "-c",
        "import sys,json;from provlab.containment import analyze;print(json.dumps(analyze(json.load(sys.stdin))))",
      ],
      { input: JSON.stringify(r), encoding: "utf8" },
    );
    assert.equal(p.status, 0, p.stderr);
    assert.deepEqual(analyze(r), JSON.parse(p.stdout));
  }
  for (const bad of [null, [], {}, { ...control, extra: 1 }])
    assert.throws(() => analyze(bad));
});
