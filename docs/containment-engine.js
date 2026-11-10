/* Bounded single-CQ comparison. Original implementation; no dependency on a server. */
export { parseJSON } from "./engine.js";
const own = (o, k) => Object.hasOwn(o, k),
  name = (x) =>
    typeof x === "string" && /^[A-Za-z_][A-Za-z_0-9]{0,15}$/.test(x),
  obj = (x) => x !== null && typeof x === "object" && !Array.isArray(x),
  keys = (x, ks) =>
    obj(x) && Object.keys(x).sort().join("|") === [...ks].sort().join("|"),
  clone = (x) => JSON.parse(JSON.stringify(x)),
  equal = (a, b) => JSON.stringify(a) === JSON.stringify(b),
  unique = (x) => [...new Set(x)],
  vs = (q) =>
    unique(
      q.body.flatMap((a) =>
        a.terms.filter((t) => own(t, "var")).map((t) => t.var),
      ),
    ),
  constants = (qs) =>
    unique(
      qs.flatMap((q) =>
        q.body.flatMap((a) =>
          a.terms.filter((t) => own(t, "const")).map((t) => t.const),
        ),
      ),
    ).sort(),
  key = (t) => (own(t, "var") ? "v:" + t.var : "c:" + t.const),
  term = (k) =>
    k.startsWith("v:") ? { var: k.slice(2) } : { const: k.slice(2) },
  atomKey = (a) => JSON.stringify([a.relation, a.terms.map(key)]),
  error = (s) => {
    throw new Error(s);
  },
  record = (entries) => Object.fromEntries(entries);
function* product(values, n, p = []) {
  if (!n) {
    yield p;
    return;
  }
  for (const v of values) yield* product(values, n - 1, [...p, v]);
}
export function validate(request) {
  if (!keys(request, ["schema", "left", "right"]))
    error("comparison requires exactly schema,left,right");
  const schema = request.schema;
  if (!Array.isArray(schema) || schema.length < 1 || schema.length > 3)
    error("schema length1..3");
  const relations = new Map();
  for (const r of schema) {
    if (
      !keys(r, ["name", "arity"]) ||
      !name(r.name) ||
      relations.has(r.name) ||
      !Number.isInteger(r.arity) ||
      r.arity < 1 ||
      r.arity > 3
    )
      error("unique relation name and arity1..3 required");
    relations.set(r.name, r.arity);
  }
  const queries = [];
  for (const s of ["left", "right"]) {
    const q = request[s];
    if (!keys(q, ["head", "body"])) error("query requires head and body");
    const { head, body } = q;
    if (
      !Array.isArray(head) ||
      head.length > 2 ||
      head.some((v) => !name(v)) ||
      unique(head).length !== head.length
    )
      error("head needs0..2 distinct variables");
    if (!Array.isArray(body) || body.length < 1 || body.length > 4)
      error("body length1..4");
    for (const a of body) {
      if (!keys(a, ["relation", "terms"]) || !relations.has(a.relation))
        error("atom requires known relation and terms");
      if (
        !Array.isArray(a.terms) ||
        a.terms.length !== relations.get(a.relation)
      )
        error("atom arity mismatch");
      for (const t of a.terms)
        if (
          !obj(t) ||
          Object.keys(t).length !== 1 ||
          !["var", "const"].includes(Object.keys(t)[0]) ||
          !name(Object.values(t)[0])
        )
          error("term needs exactly var or const with short ASCII name");
    }
    const vars = vs(q);
    if (vars.length > 4 || head.some((h) => !vars.includes(h)))
      error("unsafe head or more than4 variables");
    queries.push(q);
  }
  if (queries[0].head.length !== queries[1].head.length)
    error("head arities must agree");
  if (constants(queries).length > 2) error("at most2 literal constants");
  return clone(request);
}
function maps(source, target, literals) {
  const vars = vs(source),
    values = [
      ...vs(target).map((v) => "v:" + v),
      ...literals.map((c) => "c:" + c),
    ],
    out = [];
  for (const assignment of product(values, vars.length)) {
    const binding = new Map(vars.map((v, i) => [v, assignment[i]])),
      image = (t) => (own(t, "var") ? binding.get(t.var) : "c:" + t.const),
      head = source.head.map((v) => image({ var: v })),
      hp = equal(
        head,
        target.head.map((v) => "v:" + v),
      ),
      checks = source.body.map((a, i) => {
        const row = {
            relation: a.relation,
            terms: a.terms.map((t) => term(image(t))),
          },
          ids = target.body.flatMap((b, j) =>
            atomKey(b) === atomKey(row) ? [j] : [],
          );
        return {
          source_atom: i,
          image: row,
          target_atoms: ids,
          matched: !!ids.length,
        };
      });
    out.push({
      mapping: record(vars.map((v) => [v, term(binding.get(v))])),
      head_image: head.map(term),
      head_preserved: hp,
      atom_checks: checks,
      valid: hp && checks.every((c) => c.matched),
    });
  }
  return out;
}
function canonical(q, cs) {
  const facts = [];
  for (const [i, a] of q.body.entries()) {
    const values = a.terms.map(key);
    let f = facts.find(
      (f) => f.relation === a.relation && equal(f.values, values),
    );
    if (!f) {
      f = { relation: a.relation, values, source_atoms: [] };
      facts.push(f);
    }
    f.source_atoms.push(i);
  }
  return {
    domain: [...vs(q).map((v) => "v:" + v), ...cs.map((c) => "c:" + c)].sort(),
    facts,
    frozen_head: q.head.map((v) => "v:" + v),
  };
}
function evaluate(q, db) {
  let partials = [{ binding: new Map(), uses: [] }];
  for (const a of q.body) {
    const next = [];
    for (const p of partials)
      for (const [fi, f] of db.facts.entries()) {
        if (a.relation !== f.relation) continue;
        const b = new Map(p.binding);
        let valid = true;
        for (let i = 0; i < a.terms.length; i++) {
          const t = a.terms[i],
            v = f.values[i];
          if (own(t, "const")) {
            if (v !== "c:" + t.const) {
              valid = false;
              break;
            }
          } else {
            if (b.has(t.var) && b.get(t.var) !== v) {
              valid = false;
              break;
            }
            b.set(t.var, v);
          }
        }
        if (valid) next.push({ binding: b, uses: [...p.uses, fi] });
      }
    partials = next;
  }
  const vars = vs(q),
    cmp = (a, b) => {
      for (let i = 0; i < a.length; i++) {
        if (a[i] < b[i]) return -1;
        if (a[i] > b[i]) return 1;
      }
      return 0;
    };
  partials.sort(
    (a, b) =>
      cmp(
        vars.map((v) => a.binding.get(v)),
        vars.map((v) => b.binding.get(v)),
      ) || cmp(a.uses, b.uses),
  );
  const rows = partials.map((p) => ({
      binding: record(vars.map((v) => [v, p.binding.get(v)])),
      tuple: q.head.map((h) => p.binding.get(h)),
      fact_uses: p.uses,
      exponents: db.facts.map((_, i) => p.uses.filter((f) => f === i).length),
    })),
    outputs = unique(rows.map((r) => JSON.stringify(r.tuple)))
      .map(JSON.parse)
      .sort(cmp),
    answers = outputs.map((output) => {
      const ids = rows.flatMap((r, i) => (equal(r.tuple, output) ? [i] : []));
      return {
        tuple: output,
        derivation_indices: ids,
        set_present: true,
        uniform_bag_multiplicity: ids.length * 2 ** q.body.length,
      };
    });
  return { derivations: rows, answers };
}
function direction(source, target, cs, sl, tl) {
  const candidates = maps(source, target, cs),
    ids = candidates.flatMap((c, i) => (c.valid ? [i] : [])),
    db = canonical(target, cs);
  return {
    source: sl,
    target: tl,
    containment: tl + " ⊆ " + sl,
    map_direction: sl + " → " + tl,
    candidates,
    valid_candidate_indices: ids,
    mapping_count: ids.length,
    contained: !!ids.length,
    canonical_database: db,
    target_evaluation: evaluate(target, db),
    source_evaluation: evaluate(source, db),
    counterexample_tuple: ids.length ? null : [...db.frozen_head],
  };
}
function minimize(q, cs) {
  const atlas = [];
  for (let mask = 0; mask < 2 ** q.body.length; mask++) {
    const ids = q.body.flatMap((a, i) => ((mask >> i) & 1 ? [i] : [])),
      sub = { head: q.head, body: ids.map((i) => q.body[i]) },
      missing = q.head.filter((h) => !vs(sub).includes(h)),
      safe = !!ids.length && !missing.length,
      valid = safe
        ? maps(q, sub, cs)
            .filter((c) => c.valid)
            .map((c) => c.mapping)
        : [];
    atlas.push({
      mask,
      retained_atoms: ids,
      missing_head_variables: missing,
      safe_nonempty: safe,
      mapping_count: valid.length,
      first_mapping: valid[0] ?? null,
      set_equivalent: !!valid.length,
      minimum: false,
    });
  }
  const n = Math.min(
      ...atlas
        .filter((a) => a.set_equivalent)
        .map((a) => a.retained_atoms.length),
    ),
    ms = [];
  for (const a of atlas) {
    a.minimum = a.set_equivalent && a.retained_atoms.length === n;
    if (a.minimum) ms.push(a.mask);
  }
  return { minimum_atom_count: n, minimum_masks: ms, atlas };
}
export function analyze(request) {
  const input = validate(request),
    cs = constants([input.left, input.right]),
    lr = direction(input.right, input.left, cs, "right", "left"),
    rl = direction(input.left, input.right, cs, "left", "right");
  return {
    schema: "provlab-containment-v1",
    input,
    literal_constants: cs,
    directions: [lr, rl],
    set_equivalent: lr.contained && rl.contained,
    minimization: {
      left: minimize(input.left, cs),
      right: minimize(input.right, cs),
    },
    limits: [...LIMITS],
  };
}

const LIMITS = [
  "Two safe positive single conjunctive queries on one supplied relational schema. Set semantics only: no union, inequalities, negation, recursion, NULL or database dependencies.",
  "One to three relations of arity1..3. Each body has1..4 atom occurrences and at most4 variables; both ordered heads have the same arity0..2 and distinct variables.",
  "At most2 distinct literal constants across the query pair. Constants are fixed; variables may merge and may map to constants. Head positions must be preserved.",
  "Containment left \u2286 right requires a homomorphism right \u2192 left. Matching one supplied database is not the containment test.",
  "Canonical values v:name are fresh frozen variable symbols; c:name are distinct literal symbols. All supplied constants remain available in the finite domain even when absent from the canonical facts.",
  "Every safe nonempty atom subset is checked. Empty bodies and subsets that lose a head variable are explicitly outside the minimization candidate contract.",
  "Set-equivalent minimization is not permission to preserve bag multiplicities or natural-polynomial provenance. Canonical bag probes use uniform base multiplicity2 and are examples, not a bag-equivalence decision procedure.",
  "Classical Chandra-Merlin homomorphism and core theory in bounded syntax, not new theory, arbitrary SQL optimization, industrial scale or a guarantee about an AI system.",
];
