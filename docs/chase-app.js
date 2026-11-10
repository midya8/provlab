import { analyze, parseJSON } from "./chase-engine.js";
const $ = (id) => document.getElementById(id),
  el = (tag, text) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    return e;
  },
  term = (t) => (Object.hasOwn(t, "var") ? t.var : '"' + t.const + '"'),
  atom = (a) => a.relation + "(" + a.terms.map(term).join(", ") + ")",
  query = (q) =>
    "Q(" + q.head.join(", ") + ") :- " + q.body.map(atom).join(" ∧ "),
  tuple = (t) => "(" + t.join(", ") + ")",
  fact = (f) => f.relation + tuple(f.values),
  yes = (x) => (x ? "yes" : "no"),
  table = (target, headers, rows) => {
    const t = el("table"),
      head = el("thead"),
      tr = el("tr");
    for (const h of headers) tr.append(el("th", h));
    head.append(tr);
    t.append(head);
    const body = el("tbody");
    for (const row of rows) {
      const r = el("tr");
      if (row.selected) r.className = "selected";
      for (const c of row.cells ?? row) r.append(el("td", String(c)));
      body.append(r);
    }
    t.append(body);
    $(target).replaceChildren(t);
  },
  option = (select, value, text) => {
    const o = el("option", text);
    o.value = String(value);
    select.append(o);
  };
let controls = [],
  base = null,
  full = null,
  report = null,
  mask = 0,
  di = 0;
function dependency(d, i) {
  return (
    i +
    " / " +
    d.name +
    ": " +
    (d.kind === "key"
      ? "KEY " + d.relation + " [" + d.positions.join(", ") + "]"
      : d.body.map(atom).join(" ∧ ") + " → " + atom(d.head))
  );
}
function support(row, i) {
  const d = row.directions[i];
  return (
    (d.contained
      ? d.reason === "target-unsatisfiable"
        ? "vacuous"
        : "mapped"
      : "counterexample") +
    (row.minimum_support[i]
      ? " / minimum"
      : row.minimal_support[i]
        ? " / minimal"
        : "")
  );
}
function setup(input) {
  base = input;
  full = analyze(input);
  mask = 2 ** base.dependencies.length - 1;
  di = 0;
  $("editor").value = JSON.stringify(input, null, 2);
  $("left-query").textContent = query(base.left);
  $("right-query").textContent = query(base.right);
  $("dependencies").textContent =
    base.dependencies.map(dependency).join("\n") || "No dependencies.";
  $("subset").replaceChildren();
  for (const a of full.dependency_atlas)
    option(
      $("subset"),
      a.mask,
      a.retained_dependencies.length
        ? a.retained_dependencies
            .map((i) => base.dependencies[i].name)
            .join(" + ")
        : "No assumptions",
    );
  $("subset").value = String(mask);
  selectSubset();
  $("status").textContent = "Checked locally. No input was sent to a server.";
}
function selectSubset() {
  mask = Number($("subset").value);
  const deps = base.dependencies.filter((d, i) => (mask >> i) & 1);
  report = analyze({ ...base, dependencies: deps });
  window.chaseReport = report;
  $("download").disabled = false;
  $("step").disabled = false;
  $("subset").disabled = false;
  renderDirection();
  table(
    "atlas",
    ["Mask", "Dependencies", "Left ⊆Σ right", "Right ⊆Σ left"],
    full.dependency_atlas.map((a) => ({
      selected: a.mask === mask,
      cells: [
        a.mask,
        a.retained_dependencies
          .map((i) => base.dependencies[i].name)
          .join(" + ") || "none",
        support(a, 0),
        support(a, 1),
      ],
    })),
  );
  $("limits").replaceChildren(...report.limits.map((s) => el("li", s)));
}
function renderDirection() {
  const d = report.directions[di],
    c = d.chase;
  $("lr").setAttribute("aria-pressed", String(di === 0));
  $("rl").setAttribute("aria-pressed", String(di === 1));
  const title =
    d.reason === "target-unsatisfiable"
      ? "Contained, but only vacuously."
      : d.contained
        ? "The selected assumptions prove containment."
        : "A valid constrained counterexample survives.";
  const v = $("verdict");
  v.className = "verdict" + (!d.contained || c.failed ? " failure" : "");
  v.replaceChildren(
    el("p", d.containment),
    el("h2", title),
    el(
      "p",
      "Without assumptions: " +
        (d.unconstrained_contained ? "contained" : "not contained") +
        ". With selected assumptions: " +
        (d.contained ? "contained" : "not contained") +
        ".",
    ),
    el(
      "p",
      c.failed
        ? "The target pattern forces two distinct literals to be equal. No valid target answer exists under these assumptions."
        : report.set_equivalent
          ? "Both directions hold under the selected assumptions."
          : "This verdict is directional. The other direction is tested separately.",
    ),
  );
  $("step").replaceChildren();
  for (const s of c.trace)
    option(
      $("step"),
      s.step,
      s.step === 0
        ? "0 / initial canonical database"
        : s.step +
            " / " +
            s.event.kind +
            " / " +
            report.input.dependencies[s.event.dependency].name,
    );
  $("step").value = String(c.trace.length - 1);
  renderStep();
  $("terminal-note").textContent = c.failed
    ? "Failed chase: the terminal snapshot is not a legal model. No query evaluation or counterexample is claimed."
    : "Saturated chase: every selected dependency is satisfied. This finite database is a legal model.";
  table(
    "checks",
    [
      "Selected dependency",
      "Body matches / key pairs",
      "Violations",
      "Satisfied",
    ],
    c.dependency_checks.map((x) => [
      report.input.dependencies[x.dependency].name,
      x.body_match_count,
      x.violation_count,
      yes(x.satisfied),
    ]),
  );
  for (const [id, ev] of [
    ["source-answers", d.source_evaluation],
    ["target-answers", d.target_evaluation],
  ])
    $(id).textContent = ev
      ? ev.answers.map(tuple).join("\n") || "No answers."
      : "Not evaluated: failed chase.";
  $("witness").textContent = c.failed
    ? "Vacuity certificate: a literal clash, not a successful nonempty query match."
    : d.contained
      ? "Witness derivation " +
        d.witness_derivation +
        " maps the source query to the chased target, with ordered head " +
        tuple(c.final_state.head) +
        "."
      : "Counterexample output " +
        tuple(d.counterexample_tuple) +
        " occurs in the target query and is absent from the source query.";
  table(
    "derivations",
    ["Source derivation", "Variable binding", "Fact rows used", "Output"],
    d.source_evaluation
      ? d.source_evaluation.derivations.map((r, i) => [
          i,
          Object.entries(r.binding)
            .map(([k, v]) => k + " ↦ " + v)
            .join("; ") || "empty binding",
          r.rows.join(", "),
          tuple(r.tuple),
        ])
      : [],
  );
}
function renderStep() {
  const c = report.directions[di].chase,
    s = c.trace[Number($("step").value)],
    e = s.event;
  let note =
    "Initial query pattern. This database need not satisfy the selected assumptions yet.";
  if (e) {
    const dep = report.input.dependencies[e.dependency].name;
    note =
      e.kind === "add"
        ? dep +
          ": add " +
          fact(e.fact) +
          " from premise rows " +
          e.premise_rows.join(", ") +
          ". Binding: " +
          (Object.entries(e.binding)
            .map(([k, v]) => k + " ↦ " + v)
            .join("; ") || "empty") +
          "."
        : e.kind === "merge"
          ? dep +
            ": rows " +
            e.rows.join(" and ") +
            " agree on their key. Substitute " +
            e.replace +
            " → " +
            e.keep +
            " everywhere, including the head."
          : dep +
            ": rows " +
            e.rows.join(" and ") +
            " force " +
            e.values.join(" = ") +
            ". These distinct literals cannot merge.";
  }
  $("event").textContent = note;
  $("initial-head").textContent = tuple(c.trace[0].state.head);
  $("current-head").textContent = tuple(s.state.head);
  table(
    "facts",
    ["Row", "Fact"],
    s.state.facts.map((f, i) => [i, fact(f)]),
  );
  table(
    "aliases",
    ["Original symbol", "Current representative"],
    Object.entries(s.state.aliases),
  );
  $("domain").textContent = "Current domain: " + s.state.domain.join(", ");
}
$("control").addEventListener("change", () => {
  const c = controls[Number($("control").value)];
  $("why").textContent = c.why;
  setup(c.input);
});
$("subset").addEventListener("change", selectSubset);
$("step").addEventListener("change", renderStep);
for (const [id, i] of [
  ["lr", 0],
  ["rl", 1],
])
  $(id).addEventListener("click", () => {
    di = i;
    renderDirection();
  });
$("run").addEventListener("click", () => {
  try {
    setup(parseJSON($("editor").value));
    $("why").textContent = "Custom bounded query pair and dependencies.";
  } catch (e) {
    report = null;
    window.chaseReport = null;
    $("download").disabled = true;
    $("step").disabled = true;
    $("subset").disabled = true;
    for (const id of [
      "verdict",
      "event",
      "facts",
      "aliases",
      "checks",
      "source-answers",
      "target-answers",
      "witness",
      "derivations",
      "atlas",
      "terminal-note",
      "initial-head",
      "current-head",
      "domain",
    ])
      $(id).replaceChildren();
    $("status").textContent = "Input rejected: " + e.message;
  }
});
$("download").addEventListener("click", () => {
  const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2) + "\n"], {
        type: "application/json",
      }),
    ),
    a = el("a");
  a.href = url;
  a.download = "provlab-chase-certificate.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
try {
  const res = await fetch("chase-controls.json");
  if (!res.ok) throw Error("controls unavailable");
  controls = await res.json();
  for (const [c, i] of controls.map((c, i) => [c, i]))
    option($("control"), i, c.name);
  $("why").textContent = controls[0].why;
  setup(controls[0].input);
} catch (e) {
  $("status").textContent = "Could not start: " + e.message;
}
