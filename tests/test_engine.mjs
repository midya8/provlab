import test from "node:test";
import assert from "node:assert/strict";
import { analyze, parseJSON } from "../docs/engine.js";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
const controls = JSON.parse(
  fs.readFileSync(new URL("../docs/controls.json", import.meta.url)),
);
const py = process.env.PYTHON ?? "python";
test("complete native/browser reports: controls plus150 seeded queries", () => {
  const p = spawnSync(
    py,
    [
      "-c",
      `import json;from tools.cases import requests;from tools.make_controls import controls;from provlab import analyze;print(json.dumps([{'input':r,'report':analyze(r)}for r in [c['input']for c in controls()]+requests(150)]))`,
    ],
    { encoding: "utf8", maxBuffer: 32 * 1024 * 1024 },
  );
  assert.equal(p.status, 0, p.stderr);
  const cases = JSON.parse(p.stdout);
  for (const c of cases) assert.deepEqual(analyze(c.input), c.report);
  console.log(
    JSON.stringify({
      reports: cases.length,
      outputs: cases.reduce((n, c) => n + c.report.outputs.length, 0),
      worlds: cases.reduce(
        (n, c) => n + c.report.outputs.reduce((s, o) => s + o.worlds.length, 0),
        0,
      ),
    }),
  );
});
test("strict parser and schema", () => {
  for (const raw of ['{"a":1,"a":2}', '{"a":NaN}', "{} extra", '{"a":1.5}'])
    assert.throws(() => parseJSON(raw));
  for (const request of [null, [], {}, { ...controls[0].input, extra: 1 }])
    assert.throws(() => analyze(request));
  const c = structuredClone(controls[0].input);
  c.relations[0].rows[0].multiplicity = true;
  assert.throws(() => analyze(c));
});

test("prototype-like names are ordinary supplied identifiers", () => {
  const names = ["constructor", "toString", "__proto__", "hasOwnProperty"];
  for (const name of names) {
    const input = {
      relations: [
        {
          name: "constructor",
          arity: 1,
          rows: [
            {
              id: "toString",
              values: ["__proto__"],
              multiplicity: 1,
              probability: "1/2",
            },
          ],
        },
      ],
      query: {
        head: [name],
        branches: [[{ relation: "constructor", terms: [{ var: name }] }]],
      },
    };
    const p = spawnSync(
      py,
      [
        "-c",
        "import sys,json;from provlab import analyze;from provlab.verify import verify;r=analyze(json.load(sys.stdin));assert verify(r);print(json.dumps(r))",
      ],
      { input: JSON.stringify(input), encoding: "utf8" },
    );
    assert.equal(p.status, 0, p.stderr);
    assert.deepEqual(analyze(input), JSON.parse(p.stdout));
  }
  console.log(JSON.stringify({ prototypeLikeIdentifierReports: 4 }));
});
