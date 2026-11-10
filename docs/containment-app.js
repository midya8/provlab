import { analyze, parseJSON } from "./containment-engine.js";
const $ = (id) => document.getElementById(id),
  el = (tag, text, cls) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  },
  tuple = (x) => "(" + x.join(", ") + ")",
  term = (t) => (Object.hasOwn(t, "var") ? t.var : '"' + t.const + '"'),
  atom = (a) => a.relation + tuple(a.terms.map(term)),
  query = (q) =>
    "answer" + tuple(q.head) + " :=\n" + q.body.map(atom).join(" ∧ "),
  mapping = (m) =>
    Object.entries(m)
      .map(([k, v]) => k + " ↦ " + term(v))
      .join("; ") || "∅ (no variables)",
  polynomial = (ev, out) => {
    const counts = new Map();
    for (const i of out.derivation_indices) {
      const ex = ev.derivations[i].exponents,
        key = JSON.stringify(ex);
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return [...counts.entries()]
      .map(([k, c]) => {
        const parts = JSON.parse(k).flatMap((e, i) =>
          e ? ["f" + i + (e === 1 ? "" : "^" + e)] : [],
        );
        return (
          (c === 1 && parts.length ? "" : c + (parts.length ? "·" : "")) +
          parts.join("·")
        );
      })
      .join(" + ");
  };
let report = null,
  controls = [],
  directionIndex = 0,
  candidateIndex = 0,
  certificateURL = null;
function table(id, headers, rows) {
  const wrap = el("div", undefined, "scroll"),
    t = el("table");
  t.id = id;
  const h = el("thead"),
    tr = el("tr");
  for (const s of headers) tr.append(el("th", s));
  h.append(tr);
  t.append(h);
  const body = el("tbody");
  for (const row of rows) {
    const r = el("tr");
    for (const v of row) r.append(el("td", String(v)));
    body.append(r);
  }
  t.append(body);
  wrap.append(t);
  return wrap;
}
function block(title, k) {
  const s = el("section", undefined, "evidence-block");
  s.append(el("p", k, "eyebrow"), el("h2", title));
  return s;
}
function diagram(d, c) {
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg"),
    source = report.input[d.source],
    target = report.input[d.target],
    height = 90 + Math.max(source.body.length, target.body.length) * 65;
  svg.setAttribute("viewBox", "0 0 820 " + height);
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    d.map_direction + " atom images for selected candidate mapping",
  );
  svg.classList.add("map-diagram");
  const txt = (x, y, s, cls) => {
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", x);
    t.setAttribute("y", y);
    if (cls) t.setAttribute("class", cls);
    t.textContent = s;
    svg.append(t);
  };
  txt(24, 32, d.source.toUpperCase() + " / MAP SOURCE", "graph-heading");
  txt(475, 32, d.target.toUpperCase() + " / MAP TARGET", "graph-heading");
  for (const [q, x] of [
    [source, 24],
    [target, 475],
  ])
    for (const [i, a] of q.body.entries()) {
      const rect = document.createElementNS(ns, "rect");
      for (const [k, v] of Object.entries({
        x,
        y: 58 + i * 65,
        width: 320,
        height: 44,
        rx: 5,
      }))
        rect.setAttribute(k, v);
      svg.append(rect);
      txt(x + 12, 85 + i * 65, "#" + i + " " + atom(a));
    }
  if (c)
    for (const check of c.atom_checks) {
      const j = check.target_atoms[0];
      if (j === undefined) {
        txt(365, 86 + check.source_atom * 65, "×");
        continue;
      }
      const l = document.createElementNS(ns, "line");
      for (const [k, v] of Object.entries({
        x1: 345,
        y1: 80 + check.source_atom * 65,
        x2: 470,
        y2: 80 + j * 65,
      }))
        l.setAttribute(k, v);
      svg.prepend(l);
    }
  return svg;
}
function renderCandidate() {
  const d = report.directions[directionIndex],
    c = d.candidates[candidateIndex],
    host = $("map-evidence");
  const figure = el("div", undefined, "scroll diagram-scroll");
  figure.append(diagram(d, c));
  host.replaceChildren(figure);
  if (!c) {
    host.append(el("p", "No candidate variable maps in this finite domain."));
    return;
  }
  host.append(
    el("p", mapping(c.mapping), "map-note"),
    el(
      "p",
      "Head image " +
        tuple(c.head_image.map(term)) +
        "; required " +
        tuple(report.input[d.target].head) +
        ". " +
        (c.head_preserved
          ? "Output positions preserved."
          : "Output positions fail."),
      "map-note",
    ),
    table(
      "atom-checks",
      ["Source atom", "Image atom", "Matching target atoms", "Pass"],
      c.atom_checks.map((x) => [
        x.source_atom,
        atom(x.image),
        x.target_atoms.join(", ") || "none",
        x.matched ? "yes" : "no",
      ]),
    ),
  );
}
function renderDirection() {
  const d = report.directions[directionIndex],
    host = $("direction-evidence");
  host.replaceChildren();
  const v = el("div", undefined, "verdict" + (d.contained ? "" : " failure"));
  v.append(
    el("p", d.containment, "eyebrow"),
    el(
      "h2",
      d.contained
        ? "A reverse map proves it."
        : "This finite database disproves it.",
    ),
    el(
      "p",
      d.map_direction +
        " · " +
        d.mapping_count +
        " valid map" +
        (d.mapping_count === 1 ? "" : "s") +
        " / " +
        d.candidates.length +
        " candidate assignments.",
    ),
    el(
      "p",
      d.contained
        ? "Compose this map with any valuation of the target query. The source query returns the same ordered tuple."
        : "The target query returns " +
            tuple(d.counterexample_tuple) +
            " on its frozen canonical database; the source query does not.",
    ),
  );
  host.append(v);
  const label = el("label", "Candidate variable map", "mapping-picker"),
    select = el("select");
  select.id = "candidate";
  select.setAttribute("aria-label", "Candidate variable map");
  for (const [i, c] of d.candidates.entries()) {
    const o = el(
      "option",
      "#" +
        i +
        " · " +
        (c.valid ? "VALID" : "fails") +
        " · " +
        mapping(c.mapping),
    );
    o.value = i;
    select.append(o);
  }
  candidateIndex = d.valid_candidate_indices[0] ?? 0;
  select.value = String(candidateIndex);
  select.addEventListener("change", () => {
    candidateIndex = Number(select.value);
    renderCandidate();
  });
  label.append(select);
  host.append(label);
  const m = el("div");
  m.id = "map-evidence";
  host.append(m);
  renderCandidate();
  const db = block(
    "Freeze the target. Query it twice.",
    "03 / CANONICAL DATABASE",
  );
  db.append(
    el(
      "p",
      "v:name values are distinct frozen variable symbols. c:name values are literal constants. Every listed base fact has probe multiplicity2.",
    ),
    table(
      "canonical-facts",
      ["Token", "Relation / frozen values", "Target atom occurrences"],
      d.canonical_database.facts.map((f, i) => [
        "f" + i,
        f.relation + tuple(f.values),
        f.source_atoms.join(", "),
      ]),
    ),
  );
  for (const [label, field] of [
    [d.target, "target_evaluation"],
    [d.source, "source_evaluation"],
  ]) {
    const ev = d[field];
    db.append(
      el("h3", label.toUpperCase() + " answers"),
      table(
        label + "-answers",
        ["Output tuple", "Set present", "Bag probe", "Natural provenance"],
        ev.answers.map((a) => [
          tuple(a.tuple),
          "yes",
          a.uniform_bag_multiplicity,
          polynomial(ev, a),
        ]),
      ),
    );
    if (!ev.answers.length)
      db.append(el("p", "No output tuples.", "answer-summary"));
    db.append(
      table(
        label + "-derivations",
        ["Valuation", "Output", "Fact occurrences"],
        ev.derivations.map((row) => [
          Object.entries(row.binding)
            .map(([v, x]) => v + "=" + x)
            .join("; ") || "∅",
          tuple(row.tuple),
          row.fact_uses.map((i) => "f" + i).join(" · "),
        ]),
      ),
    );
  }
  host.append(db);
  for (const b of document.querySelectorAll(".direction-tabs button"))
    b.setAttribute(
      "aria-pressed",
      String(Number(b.dataset.direction) === directionIndex),
    );
}
function renderAtlas(side) {
  const data = report.minimization[side],
    q = report.input[side],
    s = block(
      side.toUpperCase() +
        ": " +
        data.minimum_atom_count +
        " atoms in a minimum.",
      "04 / EXACT SUBSET ATLAS",
    );
  s.append(
    el(
      "p",
      data.atlas.length +
        " atom-occurrence subsets checked. Same ordered head; empty bodies and lost head variables are not candidates.",
    ),
    table(
      side + "-atlas",
      [
        "Mask",
        "Retained atoms",
        "Safe",
        "Map count",
        "Set equivalent",
        "Minimum",
      ],
      data.atlas.map((a) => [
        a.mask,
        a.retained_atoms.join(", ") || "∅",
        a.safe_nonempty
          ? "yes"
          : a.missing_head_variables.length
            ? "lost " + a.missing_head_variables.join(", ")
            : "empty body",
        a.mapping_count,
        a.set_equivalent ? "yes" : "no",
        a.minimum ? "yes" : "no",
      ]),
    ),
  );
  const label = el("label", "Inspect subset", "atlas-choice"),
    select = el("select");
  select.id = side + "-subset";
  select.setAttribute("aria-label", side + " atom subset");
  for (const a of data.atlas) {
    const o = el(
      "option",
      "Mask " +
        a.mask +
        " · " +
        (a.minimum
          ? "minimum"
          : a.set_equivalent
            ? "equivalent"
            : a.safe_nonempty
              ? "not equivalent"
              : "not a candidate"),
    );
    o.value = a.mask;
    select.append(o);
  }
  select.value = String(data.minimum_masks[0]);
  label.append(select);
  const note = el("div");
  note.id = side + "-subset-evidence";
  function update() {
    const a = data.atlas[Number(select.value)];
    note.replaceChildren(
      el(
        "pre",
        query({ head: q.head, body: a.retained_atoms.map((i) => q.body[i]) }),
      ),
      el(
        "p",
        a.first_mapping
          ? "Full → subset: " + mapping(a.first_mapping)
          : a.safe_nonempty
            ? "No full → subset map. The subset admits extra answers on some database."
            : "Excluded: " +
              (a.missing_head_variables.length
                ? "head variables no longer occur in body."
                : "empty bodies are outside this contract."),
        "map-note",
      ),
    );
  }
  select.addEventListener("change", update);
  s.append(label, note);
  update();
  return s;
}
function render() {
  const host = $("results");
  host.replaceChildren();
  $("left-query").textContent = query(report.input.left);
  $("right-query").textContent = query(report.input.right);
  $("limits").replaceChildren(...report.limits.map((s) => el("li", s)));
  const title = el("div", undefined, "verdict");
  title.id = "equivalence";
  title.append(
    el("p", "BIDIRECTIONAL SET COMPARISON", "eyebrow"),
    el(
      "h2",
      report.set_equivalent
        ? "Equivalent under set semantics."
        : "Not the same set query.",
    ),
    el(
      "p",
      "Containment is checked in both directions. Bag counts and provenance remain separate below.",
    ),
  );
  host.append(title);
  const tabs = el("div", undefined, "direction-tabs");
  for (const [i, d] of report.directions.entries()) {
    const b = el(
      "button",
      d.containment + (d.contained ? " · holds" : " · fails"),
    );
    b.dataset.direction = i;
    b.id = "direction-" + i;
    b.setAttribute("aria-pressed", String(i === directionIndex));
    b.addEventListener("click", () => {
      directionIndex = i;
      renderDirection();
    });
    tabs.append(b);
  }
  host.append(tabs);
  const evidence = el("div");
  evidence.id = "direction-evidence";
  host.append(evidence);
  renderDirection();
  host.append(renderAtlas("left"), renderAtlas("right"));
  if (certificateURL) URL.revokeObjectURL(certificateURL);
  certificateURL = URL.createObjectURL(
    new Blob([JSON.stringify(report, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  const exportLink = el("a", "Download exact comparison report", "certificate");
  exportLink.id = "export";
  exportLink.href = certificateURL;
  exportLink.download = "provlab-containment-report.json";
  host.append(exportLink);
  window.containmentReport = report;
}
function invalidate() {
  report = null;
  window.containmentReport = null;
  $("results").replaceChildren();
  if (certificateURL) {
    URL.revokeObjectURL(certificateURL);
    certificateURL = null;
  }
}
function run(input) {
  try {
    const next = analyze(input);
    report = next;
    directionIndex = 0;
    render();
    $("status").textContent =
      "Exact comparison ready. Both directions and every atom subset checked.";
    $("status").dataset.state = "ready";
    return true;
  } catch (e) {
    invalidate();
    $("status").textContent =
      "Comparison rejected: " + e.message + " Evidence cleared.";
    $("status").dataset.state = "error";
    return false;
  }
}
$("run").addEventListener("click", () => {
  try {
    run(parseJSON($("input").value));
  } catch (e) {
    invalidate();
    $("status").textContent =
      "Comparison rejected: " + e.message + " Evidence cleared.";
    $("status").dataset.state = "error";
  }
});
fetch("containment-controls.json")
  .then((r) => {
    if (!r.ok) throw Error("controls unavailable");
    return r.json();
  })
  .then((cs) => {
    controls = cs;
    for (const [i, c] of controls.entries()) {
      const o = el("option", c.name);
      o.value = i;
      $("control").append(o);
    }
    const choose = () => {
      const c = controls[Number($("control").value)];
      $("why").textContent = c.why;
      $("input").value = JSON.stringify(c.input, null, 2);
      run(c.input);
    };
    $("control").addEventListener("change", choose);
    choose();
  })
  .catch((e) => {
    $("status").textContent = "Could not load controls: " + e.message;
  });
