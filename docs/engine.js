/* Original bounded positive-query implementation; exact BigInt fractions. */
const object = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
const keys = (x, ks) =>
  object(x) && Object.keys(x).sort().join(",") === ks.slice().sort().join(",");
const identifier = (x) =>
  typeof x === "string" && /^[A-Za-z_][A-Za-z_0-9]{0,15}$/.test(x);
const gcd = (a, b) => (b ? gcd(b, a % b) : a);
class Q {
  constructor(n, d = 1n) {
    n = BigInt(n);
    d = BigInt(d);
    if (!d) throw Error("zero denominator");
    if (d < 0n) {
      n = -n;
      d = -d;
    }
    const g = gcd(n < 0n ? -n : n, d);
    this.n = n / g;
    this.d = d / g;
  }
  static from(s) {
    const a = s.split("/");
    return new Q(a[0], a[1] ?? 1);
  }
  add(b) {
    return new Q(this.n * b.d + b.n * this.d, this.d * b.d);
  }
  mul(b) {
    return new Q(this.n * b.n, this.d * b.d);
  }
  sub(b) {
    return new Q(this.n * b.d - b.n * this.d, this.d * b.d);
  }
  pow(k) {
    let a = new Q(1);
    while (k--) a = a.mul(this);
    return a;
  }
  toString() {
    return this.d === 1n ? String(this.n) : `${this.n}/${this.d}`;
  }
}
const variables = (body) => {
  const out = [];
  for (const a of body)
    for (const t of a.terms)
      if ("var" in t && !out.includes(t.var)) out.push(t.var);
  return out;
};
function validate(d) {
  const fail = (m) => {
    throw Error(m);
  };
  if (!keys(d, ["relations", "query"]))
    fail("request needs exactly relations and query");
  if (
    !Array.isArray(d.relations) ||
    d.relations.length < 1 ||
    d.relations.length > 3
  )
    fail("relations length1..3");
  const names = [],
    ids = [],
    domain = new Set();
  const relations = d.relations.map((r) => {
    if (
      !keys(r, ["name", "arity", "rows"]) ||
      !identifier(r.name) ||
      names.includes(r.name) ||
      !Number.isInteger(r.arity) ||
      r.arity < 1 ||
      r.arity > 3
    )
      fail("invalid relation");
    names.push(r.name);
    if (!Array.isArray(r.rows)) fail("rows must be list");
    const seen = [];
    const rows = r.rows.map((f) => {
      if (
        !keys(f, ["id", "values", "multiplicity", "probability"]) ||
        !identifier(f.id) ||
        ids.includes(f.id)
      )
        fail("unique base token id required");
      ids.push(f.id);
      if (ids.length > 6) fail("at most six base tokens");
      if (
        !Array.isArray(f.values) ||
        f.values.length !== r.arity ||
        f.values.some((v) => !identifier(v)) ||
        seen.includes(JSON.stringify(f.values))
      )
        fail("unique tuples matching arity required");
      seen.push(JSON.stringify(f.values));
      f.values.forEach((v) => domain.add(v));
      if (
        !Number.isInteger(f.multiplicity) ||
        f.multiplicity < 0 ||
        f.multiplicity > 9
      )
        fail("multiplicity integer0..9 required");
      if (
        typeof f.probability !== "string" ||
        !/^(?:0|[1-9][0-9]{0,2})(?:\/[1-9][0-9]{0,2})?$/.test(f.probability)
      )
        fail("probability needs bounded rational string");
      const p = Q.from(f.probability);
      if (p.n < 0n || p.n > p.d) fail("probability outside0..1");
      return {
        id: f.id,
        values: f.values.slice(),
        multiplicity: f.multiplicity,
        probability: String(p),
      };
    });
    return { name: r.name, arity: r.arity, rows };
  });
  const q = d.query;
  if (!keys(q, ["head", "branches"]))
    fail("query needs exactly head and branches");
  if (
    !Array.isArray(q.head) ||
    q.head.length > 2 ||
    q.head.some((v) => !identifier(v)) ||
    new Set(q.head).size !== q.head.length
  )
    fail("invalid head");
  if (
    !Array.isArray(q.branches) ||
    q.branches.length < 1 ||
    q.branches.length > 4
  )
    fail("branches length1..4");
  const branches = q.branches.map((body) => {
    if (!Array.isArray(body) || body.length < 1 || body.length > 3)
      fail("body length1..3");
    const atoms = body.map((a) => {
      if (!keys(a, ["relation", "terms"]) || !names.includes(a.relation))
        fail("invalid relation atom");
      if (
        !Array.isArray(a.terms) ||
        a.terms.length !== relations[names.indexOf(a.relation)].arity
      )
        fail("atom arity mismatch");
      const terms = a.terms.map((t) => {
        if (
          !object(t) ||
          Object.keys(t).length !== 1 ||
          !["var", "const"].includes(Object.keys(t)[0]) ||
          !identifier(Object.values(t)[0])
        )
          fail("invalid tagged term");
        if ("const" in t) domain.add(t.const);
        return { ...t };
      });
      return { relation: a.relation, terms };
    });
    const vs = variables(atoms);
    if (vs.length > 4 || q.head.some((h) => !vs.includes(h)))
      fail("unsafe head or too many variables");
    return atoms;
  });
  if (domain.size > 4) fail("at most four data/query-constant values");
  return { relations, query: { head: q.head.slice(), branches } };
}
const compare = (a, b) => {
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] < b[i]) return -1;
    if (a[i] > b[i]) return 1;
  }
  return a.length - b.length;
};
const product = (xs) => xs.reduce((a, b) => a * b, 1);
function analyze(request) {
  const input = validate(request),
    facts = input.relations.flatMap((r) => r.rows),
    tokens = facts.map((f) => f.id),
    rs = new Map(input.relations.map((r) => [r.name, r])),
    domain = [
      ...new Set([
        ...facts.flatMap((f) => f.values),
        ...input.query.branches.flatMap((b) =>
          b.flatMap((a) =>
            a.terms.filter((t) => "const" in t).map((t) => t.const),
          ),
        ),
      ]),
    ].sort(),
    branches = [],
    derivations = [];
  input.query.branches.forEach((body, bi) => {
    let partials = [{ binding: {}, tokens: [] }];
    const stages = [];
    body.forEach((atom, ai) => {
      const after = [];
      for (const p of partials)
        for (const fact of rs.get(atom.relation).rows) {
          const binding = { ...p.binding };
          let ok = true;
          atom.terms.forEach((t, i) => {
            if ("const" in t) {
              if (t.const !== fact.values[i]) ok = false;
            } else {
              if (t.var in binding && binding[t.var] !== fact.values[i])
                ok = false;
              binding[t.var] = fact.values[i];
            }
          });
          if (ok) after.push({ binding, tokens: [...p.tokens, fact.id] });
        }
      const vs = variables(body.slice(0, ai + 1));
      after.sort(
        (a, b) =>
          compare(
            vs.map((v) => a.binding[v]),
            vs.map((v) => b.binding[v]),
          ) ||
          compare(
            a.tokens.map((t) => tokens.indexOf(t)),
            b.tokens.map((t) => tokens.indexOf(t)),
          ),
      );
      stages.push({ atom_index: ai, variables: vs, partials: after });
      partials = after;
    });
    for (const p of partials) {
      const exponents = tokens.map(
        (t) => p.tokens.filter((v) => v === t).length,
      );
      derivations.push({
        branch: bi,
        binding: Object.fromEntries(
          variables(body).map((v) => [v, p.binding[v]]),
        ),
        output: input.query.head.map((h) => p.binding[h]),
        tokens: p.tokens,
        exponents,
        bag_weight: product(
          exponents.map((e, i) => facts[i].multiplicity ** e),
        ),
      });
    }
    branches.push({ branch: bi, variables: variables(body), stages });
  });
  const tuples = [...new Set(derivations.map((d) => JSON.stringify(d.output)))]
      .map((s) => JSON.parse(s))
      .sort(compare),
    outputs = [];
  for (const tuple of tuples) {
    const selected = derivations.flatMap((d, i) =>
        compare(d.output, tuple) === 0 ? [i] : [],
      ),
      counts = new Map();
    for (const i of selected) {
      const e = JSON.stringify(derivations[i].exponents);
      counts.set(e, (counts.get(e) ?? 0) + 1);
    }
    const terms = [...counts]
      .map(([e, coefficient]) => ({ coefficient, exponents: JSON.parse(e) }))
      .sort((a, b) => -compare(a.exponents, b.exponents));
    const masks = [
        ...new Set(
          terms.map((t) =>
            t.exponents.reduce((m, e, i) => m | (e ? 1 << i : 0), 0),
          ),
        ),
      ].sort((a, b) => a - b),
      minimal = masks.filter(
        (w) => !masks.some((v) => v !== w && (v & w) === v),
      );
    const worlds = [];
    let probability = new Q(0),
      arithmetic = new Q(0);
    for (let mask = 0; mask < 1 << tokens.length; mask++) {
      const active = selected.filter((i) =>
        derivations[i].exponents.every((e, j) => !e || (mask >> j) & 1),
      );
      let mass = new Q(1);
      facts.forEach((f, i) => {
        const p = Q.from(f.probability);
        mass = mass.mul((mask >> i) & 1 ? p : new Q(1).sub(p));
      });
      const holds = active.length > 0;
      if (holds) probability = probability.add(mass);
      worlds.push({
        mask,
        present: tokens.filter((t, i) => (mask >> i) & 1),
        derivation_indices: active,
        holds,
        mass: String(mass),
        included_mass: holds ? String(mass) : "0",
      });
    }
    for (const t of terms) {
      let a = new Q(t.coefficient);
      t.exponents.forEach((e, i) => {
        a = a.mul(Q.from(facts[i].probability).pow(e));
      });
      arithmetic = arithmetic.add(a);
    }
    outputs.push({
      tuple,
      derivation_indices: selected,
      terms,
      derivation_count: selected.length,
      bag_multiplicity: selected.reduce(
        (s, i) => s + derivations[i].bag_weight,
        0,
      ),
      used_tokens: tokens.filter((t, i) =>
        terms.some((term) => term.exponents[i]),
      ),
      witnesses: masks.map((m) => tokens.filter((t, i) => (m >> i) & 1)),
      minimal_witnesses: minimal.map((m) =>
        tokens.filter((t, i) => (m >> i) & 1),
      ),
      worlds,
      presence_probability: String(probability),
      arithmetic_probability_substitution: String(arithmetic),
      substitution_matches_here: String(probability) === String(arithmetic),
    });
  }
  return {
    schema: "provlab-v1",
    input,
    domain,
    tokens,
    branches,
    derivations,
    outputs,
    limits: limits.slice(),
  };
}

const limits = [
  "At most six distinct base-tuple tokens across one to three supplied relations, arity1..3; at most four distinct values including query constants.",
  "One to four union-all conjunctive branches, one to three atoms per branch, at most four variables per branch; a common safe head has zero to two distinct variables.",
  "Positive finite queries only. No SQL parser, recursion, negation, aggregation, NULL, updates, inferred schema or correlated base events.",
  "How-provenance uses natural coefficients and preserves repeated token powers. Duplicate branches and repeated atoms are not silently idempotent.",
  "Bag multiplicities and existence probabilities are separate interpretations of the same supplied tokens. A multiplicity is not a probability.",
  "Exact answer-presence probability sums Boolean-query worlds under explicitly independent base-tuple events. Reusing a token is the same event, not a fresh draw.",
  "Ordinary arithmetic substitution of input probabilities into a how-provenance polynomial is shown only as a generally invalid marginal-probability contrast.",
  "Classical provenance semirings and exhaustive bounded inference, not new theory, a scalable database engine, calibrated data, causal effects or a verified AI agent.",
];
export function parseJSON(raw) {
  if (new TextEncoder().encode(raw).length > 65536)
    throw Error("input exceeds65536 bytes");
  let p = 0;
  const ws = () => {
    while (/[ \t\r\n]/.test(raw[p] ?? "") && p < raw.length) p++;
  };
  function string() {
    const start = p++;
    while (p < raw.length) {
      if (raw[p] === "\\") {
        p += 2;
        continue;
      }
      if (raw[p++] === '"') return JSON.parse(raw.slice(start, p));
    }
    throw Error("unterminated string");
  }
  function value() {
    ws();
    const c = raw[p];
    if (c === '"') return string();
    if (c === "{") {
      p++;
      const keys = new Set(),
        out = Object.create(null);
      ws();
      if (raw[p] === "}") {
        p++;
        return out;
      }
      while (true) {
        ws();
        if (raw[p] !== '"') throw Error("object key must be string");
        const k = string();
        if (keys.has(k)) throw Error("duplicate JSON key");
        keys.add(k);
        ws();
        if (raw[p++] !== ":") throw Error("missing colon");
        out[k] = value();
        ws();
        const sep = raw[p++];
        if (sep === "}") return out;
        if (sep !== ",") throw Error("missing comma");
      }
    }
    if (c === "[") {
      p++;
      const out = [];
      ws();
      if (raw[p] === "]") {
        p++;
        return out;
      }
      while (true) {
        out.push(value());
        ws();
        const sep = raw[p++];
        if (sep === "]") return out;
        if (sep !== ",") throw Error("missing comma");
      }
    }
    for (const [token, v] of [
      ["true", true],
      ["false", false],
      ["null", null],
    ])
      if (raw.startsWith(token, p)) {
        p += token.length;
        return v;
      }
    const number = raw
      .slice(p)
      .match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (!number) throw Error("invalid JSON value");
    p += number[0].length;
    if (/[.eE]/.test(number[0])) throw Error("integer JSON number required");
    const n = Number(number[0]);
    if (!Number.isFinite(n)) throw Error("nonfinite JSON number");
    return n;
  }
  const result = value();
  ws();
  if (p !== raw.length) throw Error("trailing JSON content");
  return result;
}

export { analyze, validate };
