/* Finite full-rule/key chase. All processing stays in this browser. */
import { validate as pairValidate } from "./containment-engine.js";
export { parseJSON } from "./engine.js";
const own = (o, k) => Object.hasOwn(o, k),
  obj = (x) => x !== null && typeof x === "object" && !Array.isArray(x),
  keys = (x, ks) =>
    obj(x) && Object.keys(x).sort().join("|") === [...ks].sort().join("|"),
  name = (x) =>
    typeof x === "string" && /^[A-Za-z_][A-Za-z_0-9]{0,15}$/.test(x),
  clone = (x) => JSON.parse(JSON.stringify(x)),
  unique = (x) => [...new Set(x)],
  error = (s) => {
    throw Error(s);
  },
  eq = (a, b) => JSON.stringify(a) === JSON.stringify(b),
  cmp = (a, b) => {
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      if (a[i] < b[i]) return -1;
      if (a[i] > b[i]) return 1;
    }
    return a.length - b.length;
  },
  vars = (body) =>
    unique(
      body.flatMap((a) =>
        a.terms.filter((t) => own(t, "var")).map((t) => t.var),
      ),
    ),
  sym = (t) => (own(t, "var") ? "n:" + t.var : "c:" + t.const),
  fkey = (f) => JSON.stringify([f.relation, f.values]),
  sorted = (fs) =>
    [...new Map(fs.map((f) => [fkey(f), f])).values()].sort((a, b) =>
      cmp([a.relation, ...a.values], [b.relation, ...b.values]),
    );
function constants(d) {
  const atoms = ["left", "right"]
    .flatMap((s) => d[s].body)
    .concat(
      d.dependencies
        .filter((d) => d.kind === "full")
        .flatMap((d) => [...d.body, d.head]),
    );
  return unique(
    atoms.flatMap((a) =>
      a.terms.filter((t) => own(t, "const")).map((t) => t.const),
    ),
  ).sort();
}
export function validate(request) {
  if (!keys(request, ["schema", "left", "right", "dependencies"]))
    error("requires exactly schema,left,right,dependencies");
  const data = pairValidate(
    Object.fromEntries(["schema", "left", "right"].map((k) => [k, request[k]])),
  );
  if (data.schema.some((r) => r.arity > 2)) error("chase relation arities1..2");
  if (["left", "right"].some((s) => vars(data[s].body).length > 3))
    error("chase queries have at most3 variables");
  const deps = request.dependencies;
  if (!Array.isArray(deps) || deps.length > 3) error("dependencies length0..3");
  const names = new Set(),
    rs = new Map(data.schema.map((r) => [r.name, r.arity]));
  data.dependencies = deps.map((d) => {
    if (
      !obj(d) ||
      !name(d.name) ||
      names.has(d.name) ||
      !["full", "key"].includes(d.kind)
    )
      error("unique dependency names and full/key kinds required");
    names.add(d.name);
    if (d.kind === "key") {
      if (
        !keys(d, ["name", "kind", "relation", "positions"]) ||
        !rs.has(d.relation)
      )
        error("key requires known relation and positions");
      const ps = d.positions;
      if (
        !Array.isArray(ps) ||
        !ps.length ||
        ps.some(
          (i) => !Number.isInteger(i) || i < 0 || i >= rs.get(d.relation),
        ) ||
        unique(ps).length !== ps.length
      )
        error("key positions must be unique valid zero-based integers");
      return {
        name: d.name,
        kind: d.kind,
        relation: d.relation,
        positions: [...ps].sort(),
      };
    }
    if (
      !keys(d, ["name", "kind", "body", "head"]) ||
      !Array.isArray(d.body) ||
      !d.body.length ||
      d.body.length > 2
    )
      error("full rule requires1..2 body atoms and a single head atom");
    const query = { head: [], body: [...d.body, d.head] },
      normalized = pairValidate({
        schema: data.schema,
        left: query,
        right: query,
      }).left.body,
      body = normalized.slice(0, -1),
      head = normalized.at(-1);
    if (
      vars(normalized).length > 3 ||
      head.terms.some((t) => own(t, "var") && !vars(body).includes(t.var))
    )
      error("full rule head variables must be bound and total variables<=3");
    return { name: d.name, kind: d.kind, body, head };
  });
  if (constants(data).length > 2)
    error("at most2 literal constants across query pair and rules");
  return data;
}
function joins(body, facts) {
  let ps = [{ binding: new Map(), rows: [] }];
  for (const atom of body) {
    const next = [];
    for (const p of ps)
      for (const [i, f] of facts.entries()) {
        if (atom.relation !== f.relation) continue;
        const b = new Map(p.binding);
        let ok = true;
        for (const [j, t] of atom.terms.entries()) {
          const v = f.values[j];
          if (own(t, "const")) {
            if (v !== "c:" + t.const) {
              ok = false;
              break;
            }
          } else {
            if (b.has(t.var) && b.get(t.var) !== v) {
              ok = false;
              break;
            }
            b.set(t.var, v);
          }
        }
        if (ok) next.push({ binding: b, rows: [...p.rows, i] });
      }
    ps = next;
  }
  const vs = vars(body);
  ps.sort((a, b) =>
    cmp(
      vs.map((v) => a.binding.get(v)),
      vs.map((v) => b.binding.get(v)),
    ),
  );
  return ps.map((p) => ({
    binding: Object.fromEntries(vs.map((v) => [v, p.binding.get(v)])),
    rows: p.rows,
  }));
}
function actions(deps, facts) {
  const events = [],
    checks = [],
    lookup = new Set(facts.map(fkey));
  for (const [di, d] of deps.entries()) {
    let count = 0;
    const es = [];
    if (d.kind === "full") {
      const matches = joins(d.body, facts);
      count = matches.length;
      for (const m of matches) {
        const f = {
          relation: d.head.relation,
          values: d.head.terms.map((t) =>
            own(t, "var") ? m.binding[t.var] : "c:" + t.const,
          ),
        };
        if (!lookup.has(fkey(f)))
          es.push({
            dependency: di,
            kind: "add",
            binding: m.binding,
            premise_rows: m.rows,
            fact: f,
          });
      }
    } else {
      for (let i = 0; i < facts.length; i++)
        for (let j = i + 1; j < facts.length; j++) {
          const a = facts[i],
            b = facts[j];
          if (
            a.relation !== d.relation ||
            b.relation !== d.relation ||
            d.positions.some((p) => a.values[p] !== b.values[p])
          )
            continue;
          count++;
          for (let p = 0; p < a.values.length; p++) {
            const u = a.values[p],
              v = b.values[p];
            if (u === v) continue;
            const clash = u.startsWith("c:") && v.startsWith("c:"),
              e = {
                dependency: di,
                kind: clash ? "clash" : "merge",
                rows: [i, j],
                position: p,
                values: [u, v],
              };
            if (!clash) {
              [e.keep, e.replace] = [u, v].sort();
            }
            es.push(e);
          }
        }
    }
    checks.push({
      dependency: di,
      body_match_count: count,
      violation_count: es.length,
      satisfied: !es.length,
    });
    events.push(...es);
  }
  return [events, checks];
}
function chase(q, deps, cs) {
  const symbols = [
      ...vars(q.body).map((v) => "n:" + v),
      ...cs.map((c) => "c:" + c),
    ].sort(),
    aliases = new Map(symbols.map((s) => [s, s]));
  let facts = sorted(
      q.body.map((a) => ({ relation: a.relation, values: a.terms.map(sym) })),
    ),
    failure = null;
  const find = (s) => {
      while (aliases.get(s) !== s) s = aliases.get(s);
      return s;
    },
    snap = () => ({
      domain: unique(symbols.map(find)).sort(),
      facts: clone(facts),
      aliases: Object.fromEntries(symbols.map((s) => [s, find(s)])),
      head: q.head.map((v) => find("n:" + v)),
    });
  const trace = [{ step: 0, event: null, state: snap() }];
  for (;;) {
    const [events] = actions(deps, facts);
    if (!events.length) break;
    const e = events[0];
    if (e.kind === "add") facts = sorted([...facts, e.fact]);
    else if (e.kind === "merge") {
      aliases.set(e.replace, e.keep);
      facts = sorted(
        facts.map((f) => ({
          relation: f.relation,
          values: f.values.map(find),
        })),
      );
    } else failure = e;
    trace.push({ step: trace.length, event: e, state: snap() });
    if (failure) break;
    if (trace.length > 380) error("finite chase bound violated");
  }
  return {
    failed: failure !== null,
    failure,
    trace,
    final_state: trace.at(-1).state,
    dependency_checks: actions(deps, facts)[1],
  };
}
function evaluate(q, state) {
  const derivations = joins(q.body, state.facts);
  for (const r of derivations) r.tuple = q.head.map((v) => r.binding[v]);
  return {
    derivations,
    answers: unique(derivations.map((r) => JSON.stringify(r.tuple)))
      .map(JSON.parse)
      .sort(cmp),
  };
}
function direction(data, src, dst, deps, cs) {
  const c = chase(data[dst], deps, cs),
    initial = c.trace[0].state,
    state = c.final_state,
    base = evaluate(data[src], initial).answers.some((a) =>
      eq(a, initial.head),
    ),
    se = c.failed ? null : evaluate(data[src], state),
    te = c.failed ? null : evaluate(data[dst], state),
    witness = c.failed
      ? -1
      : se.derivations.findIndex((r) => eq(r.tuple, state.head)),
    contained = c.failed || witness >= 0;
  return {
    source: src,
    target: dst,
    containment: dst + " ⊆Σ " + src,
    unconstrained_contained: base,
    contained,
    reason: c.failed
      ? "target-unsatisfiable"
      : contained
        ? "mapped"
        : "counterexample",
    chase: c,
    source_evaluation: se,
    target_evaluation: te,
    witness_derivation: witness < 0 ? null : witness,
    counterexample_tuple: contained ? null : state.head,
  };
}
export function analyze(request) {
  const input = validate(request),
    cs = constants(input),
    pairs = [
      ["right", "left"],
      ["left", "right"],
    ],
    directions = pairs.map(([s, t]) =>
      direction(input, s, t, input.dependencies, cs),
    ),
    atlas = [];
  for (let mask = 0; mask < 2 ** input.dependencies.length; mask++) {
    const ids = input.dependencies.flatMap((d, i) =>
        (mask >> i) & 1 ? [i] : [],
      ),
      deps = ids.map((i) => input.dependencies[i]),
      ds = pairs
        .map(([s, t]) => direction(input, s, t, deps, cs))
        .map((d) => ({
          contained: d.contained,
          reason: d.reason,
          chase_steps: d.chase.trace.length - 1,
          final_fact_count: d.chase.final_state.facts.length,
        }));
    atlas.push({
      mask,
      retained_dependencies: ids,
      directions: ds,
      set_equivalent: ds.every((d) => d.contained),
      minimal_support: [false, false],
      minimum_support: [false, false],
    });
  }
  const minima = [0, 1].map((di) => {
    const ss = atlas.filter((a) => a.directions[di].contained),
      n = ss.length
        ? Math.min(...ss.map((a) => a.retained_dependencies.length))
        : null;
    for (const a of ss) {
      a.minimal_support[di] = !ss.some(
        (b) => b.mask !== a.mask && (b.mask & a.mask) === b.mask,
      );
      a.minimum_support[di] = a.retained_dependencies.length === n;
    }
    return n;
  });
  return {
    schema: "provlab-chase-v1",
    input,
    literal_constants: cs,
    directions,
    set_equivalent: directions.every((d) => d.contained),
    minimum_support_sizes: minima,
    dependency_atlas: atlas,
    limits: [...LIMITS],
  };
}
const LIMITS = [
  "Constraint-relative set containment for two safe positive single conjunctive queries. Schema1..3 relations, arity1..2,1..4 atom occurrences/query, at most3 variables/query, equally long ordered heads0..2 distinct safe variables.",
  "Up to3 named dependencies: a full single-head tuple-generating rule with1..2 body atoms and at most3 variables, or a relational key with a nonempty set of zero-based positions. All rule-head variables must occur in its body.",
  "At most2 distinct literal constants across both queries and all rules. All query variables, including output variables, start as mergeable n:name tableau symbols. Literal c:name values alone are rigid.",
  "Keys substitute in every fact AND the output tuple. Two unequal literal constants cannot merge: that target query is unsatisfiable under the selected dependencies, so its containment is vacuous, not a successful nonempty rewrite.",
  "A failed initial canonical database is not a constrained counterexample. Only a nonfailed saturated database satisfying all selected dependencies can witness a missing source answer.",
  "Full rules introduce no new symbols. At most5 initial symbols and75 possible unary/binary facts give a crude bound of379 add/merge steps: at most4 merges and5 phases of at most75 additions. Literal clash is a terminal failure step.",
  "Every dependency subset is tested in both directions. Minimal supports mean inclusion-minimal; minimum supports mean smallest cardinality. Supports can work by target unsatisfiability, which is labeled separately.",
  "Classical chase/universal-model theory in bounded syntax. No existential rules, arbitrary chase-termination claim, SQL parser, SQL NULL, bags, provenance-preserving optimization, arbitrary EGD, denial rule or global query-minimization guarantee.",
];
