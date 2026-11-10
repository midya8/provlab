import { analyze, parseJSON } from "./engine.js";
const $ = (id) => document.getElementById(id),
  el = (tag, text, cls) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  },
  set = (x) => "{" + x.join(", ") + "}",
  tuple = (x) => "(" + x.join(", ") + ")";
let controls,
  report = null,
  chosen = 0,
  worldMask = 0;
function table(id, headers, rows) {
  const wrapper = el("div", undefined, "scroll"),
    t = el("table");
  t.id = id;
  const th = el("thead"),
    tr = el("tr");
  headers.forEach((h) => tr.append(el("th", h)));
  th.append(tr);
  t.append(th);
  const body = el("tbody");
  rows.forEach((values) => {
    const r = el("tr");
    values.forEach((v) => r.append(el("td", String(v))));
    body.append(r);
  });
  t.append(body);
  wrapper.append(t);
  return wrapper;
}
function polynomial(o) {
  return o.terms
    .map((t) => {
      const parts = t.exponents.flatMap((e, i) =>
        e ? [report.tokens[i] + (e === 1 ? "" : "^" + e)] : [],
      );
      return (
        (t.coefficient === 1 && parts.length
          ? ""
          : String(t.coefficient) + (parts.length ? "·" : "")) + parts.join("·")
      );
    })
    .join(" + ");
}
function renderInput() {
  const rows = report.input.relations.flatMap((r) =>
    r.rows.map((f) => [
      f.id,
      r.name + tuple(f.values),
      f.multiplicity,
      f.probability,
    ]),
  );
  const tbody = $("facts").querySelector("tbody");
  tbody.replaceChildren();
  rows.forEach((values) => {
    const tr = el("tr");
    values.forEach((v) => tr.append(el("td", String(v))));
    tbody.append(tr);
  });
  const q = report.input.query;
  const atom = (a) =>
    a.relation +
    "(" +
    a.terms.map((t) => ("var" in t ? t.var : '"' + t.const + '"')).join(", ") +
    ")";
  $("query").textContent =
    "answer" +
    tuple(q.head) +
    " :=\n" +
    q.branches
      .map((b, i) => (i ? "UNION ALL\n" : "") + b.map(atom).join(" ∧ "))
      .join("\n");
  $("limits").replaceChildren(...report.limits.map((s) => el("li", s)));
}
function svgGraph(o) {
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 620 220");
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    "Base tokens feed polynomial terms; alternatives sum to the answer. Repeated exponents remain visible.",
  );
  const label = (x, y, s) => {
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", x);
    t.setAttribute("y", y);
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("class", "graph-label");
    t.textContent = s;
    svg.append(t);
  };
  const line = (x1, y1, x2, y2) => {
    const l = document.createElementNS(ns, "line");
    for (const [k, v] of Object.entries({
      x1,
      y1,
      x2,
      y2,
      stroke: "#a5bba9",
      "stroke-width": 1.5,
    }))
      l.setAttribute(k, v);
    svg.append(l);
  };
  const count = Math.max(report.tokens.length, o.terms.length, 1);
  if (count > 8) {
    svg.remove();
    return el("p", "All terms are listed in the polynomial and certificate.");
  }
  report.tokens.forEach((t, i) => {
    const y = 20 + (i * 180) / Math.max(report.tokens.length - 1, 1);
    o.terms.forEach((term, j) => {
      if (term.exponents[i])
        line(65, y + 3, 295, 25 + (j * 170) / Math.max(o.terms.length - 1, 1));
    });
    label(42, y + 7, t);
  });
  o.terms.forEach((term, j) => {
    const y = 25 + (j * 170) / Math.max(o.terms.length - 1, 1);
    line(325, y, 550, 110);
    label(
      310,
      y - 6,
      (term.coefficient > 1 ? term.coefficient + "·" : "") +
        term.exponents
          .flatMap((e, i) =>
            e ? [report.tokens[i] + (e > 1 ? "^" + e : "")] : [],
          )
          .join("·"),
    );
  });
  label(560, 105, "Σ");
  label(560, 129, tuple(o.tuple));
  return svg;
}
function renderOutput() {
  const root = $("results");
  root.replaceChildren();
  if (!report) return;
  const head = el("div", undefined, "result-head"),
    intro = el("div");
  intro.append(
    el("p", "03 / FOLLOW THE DERIVATION", "eyebrow"),
    el("h2", "One answer, several meanings."),
  );
  head.append(intro);
  const lab = el("label", "Output tuple"),
    select = el("select");
  select.id = "output";
  select.setAttribute("aria-label", "Output tuple");
  report.outputs.forEach((o, i) => {
    const opt = el("option", tuple(o.tuple));
    opt.value = i;
    select.append(opt);
  });
  select.value = chosen;
  select.onchange = () => {
    chosen = Number(select.value);
    worldMask = 0;
    renderOutput();
  };
  lab.append(select);
  head.append(lab);
  root.append(head);
  if (!report.outputs.length) {
    select.disabled = true;
    root.append(
      el(
        "p",
        "No result tuples are derivable in the full supplied database. A failed Boolean query has no unit tuple. There is no output certificate to select.",
        "empty",
      ),
    );
    return;
  }
  const o = report.outputs[chosen],
    metrics = el("div", undefined, "metrics");
  const values = [
    [
      "EXACT ANSWER PRESENCE",
      o.presence_probability,
      "Sum the mass of worlds where this tuple exists.",
    ],
    [
      "BAG MULTIPLICITY",
      String(o.bag_multiplicity),
      "Expand each input fact into its supplied number of copies.",
    ],
    [
      "ARITHMETIC SUBSTITUTION",
      o.arithmetic_probability_substitution,
      o.substitution_matches_here
        ? "Happens to match here. This is not a general probability rule."
        : "Does not match: arithmetic powers and sums are not Boolean events.",
    ],
  ];
  values.forEach(([label, value, description], i) => {
    const m = el("div", undefined, "metric");
    m.append(
      el("div", label, "label"),
      el("div", value, "value"),
      el("p", description),
    );
    m.querySelector(".value").id = ["probability", "bag", "arithmetic"][i];
    metrics.append(m);
  });
  root.append(metrics);
  const p = el("div", undefined, "poly");
  p.append(
    el("div", "NATURAL-COEFFICIENT HOW-PROVENANCE", "eyebrow"),
    el("code", polynomial(o)),
  );
  p.querySelector("code").id = "polynomial";
  p.append(
    el(
      "p",
      o.derivation_count +
        " valid derivations. Exponents count reuse; coefficients count repeated derivation monomials.",
    ),
  );
  root.append(p, svgGraph(o));
  const witness = el("section", undefined, "evidence");
  witness.append(el("h3", "Forget the count. Keep the event."));
  const w = el("div", undefined, "witnesses");
  for (const [label, sets, id] of [
    ["All witness sets", o.witnesses, "witnesses"],
    ["Minimal Boolean witnesses", o.minimal_witnesses, "minimal"],
  ]) {
    const d = el("div");
    d.append(el("h3", label));
    const list = el("div");
    list.id = id;
    sets.forEach((s) => list.append(el("span", set(s), "pill")));
    d.append(list);
    w.append(d);
  }
  witness.append(
    w,
    el(
      "p",
      "Used tokens " +
        set(o.used_tokens) +
        ". Removing duplicate uses gives witness sets. Removing supersets preserves existence, but loses how-provenance multiplicity.",
      "small",
    ),
  );
  root.append(witness);
  const deriv = el("details");
  deriv.id = "derivation-detail";
  deriv.append(
    el("summary", "Inspect every valid derivation and partial join"),
  );
  deriv.append(
    table(
      "derivations",
      ["#", "Branch", "Binding", "Token uses", "Bag weight"],
      o.derivation_indices.map((i) => {
        const d = report.derivations[i];
        return [
          i,
          d.branch,
          JSON.stringify(d.binding),
          d.tokens.join(" · "),
          d.bag_weight,
        ];
      }),
    ),
  );
  report.branches.forEach((b) => {
    b.stages.forEach((s) => {
      deriv.append(
        el(
          "div",
          "Branch" +
            b.branch +
            " / atom" +
            s.atom_index +
            " / " +
            s.partials.length +
            " partial bindings\n" +
            s.partials
              .map(
                (p) =>
                  JSON.stringify(p.binding) + " [" + p.tokens.join(" · ") + "]",
              )
              .join("\n"),
          "stage",
        ),
      );
    });
  });
  root.append(deriv);
  const worlds = el("section", undefined, "evidence");
  worlds.append(
    el("p", "04 / ENUMERATE THE POSSIBLE DATABASES", "eyebrow"),
    el("h3", "A repeated token never becomes a fresh draw."),
    el(
      "p",
      "Toggle the base events to select one world. Each world appears once, even when several derivations succeed.",
      "small",
    ),
  );
  const toggles = el("div", undefined, "world-controls");
  toggles.id = "toggles";
  report.tokens.forEach((t, i) => {
    const b = el("button", t);
    b.dataset.token = t;
    b.onclick = () => {
      worldMask ^= 1 << i;
      updateWorld();
    };
    toggles.append(b);
  });
  worlds.append(toggles);
  const state = el("div", undefined, "world-state");
  state.id = "world-state";
  worlds.append(state);
  worlds.append(
    table(
      "worlds",
      [
        "Mask",
        "Present tokens",
        "Holds",
        "Active derivations",
        "World mass",
        "Included mass",
      ],
      o.worlds.map((v) => [
        v.mask,
        set(v.present),
        String(v.holds),
        set(v.derivation_indices),
        v.mass,
        v.included_mass,
      ]),
    ),
  );
  root.append(worlds);
  updateWorld();
}
function updateWorld() {
  const o = report.outputs[chosen],
    w = o.worlds[worldMask];
  $("world-state").textContent =
    "World" +
    w.mask +
    " · present " +
    set(w.present) +
    " · answer " +
    (w.holds ? "exists" : "absent") +
    " · mass " +
    w.mass +
    " · counted " +
    w.included_mass;
  $("world-state").dataset.mask = w.mask;
  $("toggles")
    .querySelectorAll("button")
    .forEach((b, i) =>
      b.setAttribute("aria-pressed", String(Boolean((worldMask >> i) & 1))),
    );
  $("worlds")
    .querySelectorAll("tbody tr")
    .forEach((tr, i) => {
      tr.className =
        i === worldMask ? "selected" : !o.worlds[i].holds ? "excluded" : "";
    });
}
function run() {
  try {
    report = analyze(parseJSON($("input").value));
    window.provReport = report;
    chosen = 0;
    worldMask = 0;
    renderInput();
    renderOutput();
    $("download").disabled = false;
    $("status").textContent =
      "Exact finite replay ready · " +
      report.derivations.length +
      " derivations · " +
      report.outputs.length +
      " output tuples";
  } catch (e) {
    report = null;
    window.provReport = null;
    $("results").replaceChildren();
    $("facts").querySelector("tbody").replaceChildren();
    $("query").textContent = "";
    $("download").disabled = true;
    $("status").textContent = "Rejected: " + e.message;
  }
}
function load() {
  const c = controls[Number($("control").value)];
  $("why").textContent = c.why;
  $("input").value = JSON.stringify(c.input, null, 2);
  run();
}
$("run").onclick = run;
$("control").onchange = load;
$("download").onclick = () => {
  if (!report) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(report, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  const a = el("a");
  a.href = url;
  a.download = "provlab-certificate.json";
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
try {
  controls = await (await fetch("controls.json")).json();
  controls.forEach((c, i) => {
    const opt = el("option", c.title);
    opt.value = i;
    $("control").append(opt);
  });
  load();
} catch (e) {
  $("status").textContent = "Could not load local controls: " + e.message;
}
