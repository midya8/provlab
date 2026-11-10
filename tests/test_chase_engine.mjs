import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { spawnSync } from "node:child_process";
import { analyze, validate, parseJSON } from "../docs/chase-engine.js";
const cases = JSON.parse(
  fs.readFileSync(new URL("../docs/chase-controls.json", import.meta.url)),
);
const py = spawnSync(
  "python",
  [
    "-c",
    `import json
from provlab.chase import analyze
from tools.chase_cases import controls,requests
print(json.dumps([analyze(x)for x in[c['input']for c in controls()]+requests(100)]))`,
  ],
  { encoding: "utf8", maxBuffer: 32 * 1024 * 1024 },
);
assert.equal(py.status, 0, py.stderr);
const expected = JSON.parse(py.stdout);
test("114 complete Python/JavaScript reports match including traces and every support subset", () => {
  for (const e of expected) assert.deepEqual(analyze(e.input), e);
});
test("reserved prototype-like valid names remain data, not object inheritance", () => {
  for (const value of [
    "__proto__",
    "constructor",
    "toString",
    "hasOwnProperty",
  ]) {
    const d = structuredClone(cases[0].input);
    for (const s of ["left", "right"]) {
      d[s].head = d[s].head.map((v) => (v === "x" ? value : v));
      for (const a of d[s].body)
        for (const t of a.terms) if (t.var === "x") t.var = value;
    }
    assert.doesNotThrow(() => analyze(d));
  }
});
test("strict malformed rules, keys and JSON rejected", () => {
  for (const dep of [
    { name: "a", kind: [] },
    { name: "a", kind: "key", relation: "R", positions: [true] },
    { name: "a", kind: "key", relation: "R", positions: [0, 0] },
    {
      name: "a",
      kind: "full",
      body: [{ relation: "R", terms: [{ var: "x" }, { var: "x" }] }],
      head: { relation: "S", terms: [{ var: "x" }, { var: "y" }] },
    },
  ]) {
    const d = structuredClone(cases[0].input);
    d.dependencies = [dep];
    assert.throws(() => validate(d));
  }
  assert.throws(() => parseJSON('{"a":1,"a":2}'));
});
