"""Deterministic finite restricted full-rule/key chase with explicit tuple quotient."""

from itertools import combinations
from .chase_input import validate, all_constants, LIMITS
from .containment_input import variables


def symbol(t):
    return "n:" + t["var"] if "var" in t else "c:" + t["const"]


def fact_key(f):
    return (f["relation"], tuple(f["values"]))


def as_fact(k):
    return {"relation": k[0], "values": list(k[1])}


def joins(body, facts):
    partials = [({}, [])]
    for atom in body:
        nxt = []
        for binding, rows in partials:
            for i, f in enumerate(facts):
                if f["relation"] != atom["relation"]:
                    continue
                b = dict(binding)
                ok = True
                for t, value in zip(atom["terms"], f["values"]):
                    if "const" in t:
                        if value != "c:" + t["const"]:
                            ok = False
                            break
                    else:
                        if t["var"] in b and b[t["var"]] != value:
                            ok = False
                            break
                        b[t["var"]] = value
                if ok:
                    nxt.append((b, rows + [i]))
        partials = nxt
    vs = variables(body)
    partials.sort(key=lambda x: tuple(x[0][v] for v in vs))
    return [{"binding": {v: b[v] for v in vs}, "rows": rows} for b, rows in partials]


def actions(deps, facts):
    result = []
    checks = []
    lookup = {fact_key(f) for f in facts}
    for di, d in enumerate(deps):
        count = 0
        events = []
        if d["kind"] == "full":
            matches = joins(d["body"], facts)
            count = len(matches)
            for m in matches:
                atom = d["head"]
                f = {
                    "relation": atom["relation"],
                    "values": [
                        m["binding"][t["var"]] if "var" in t else "c:" + t["const"]
                        for t in atom["terms"]
                    ],
                }
                if fact_key(f) not in lookup:
                    events.append(
                        {
                            "dependency": di,
                            "kind": "add",
                            "binding": m["binding"],
                            "premise_rows": m["rows"],
                            "fact": f,
                        }
                    )
        else:
            rows = [i for i, f in enumerate(facts) if f["relation"] == d["relation"]]
            for i, j in combinations(rows, 2):
                a = facts[i]["values"]
                b = facts[j]["values"]
                if any(a[p] != b[p] for p in d["positions"]):
                    continue
                count += 1
                for p, (u, v) in enumerate(zip(a, b)):
                    if u == v:
                        continue
                    clash = u.startswith("c:") and v.startswith("c:")
                    event = {
                        "dependency": di,
                        "kind": "clash" if clash else "merge",
                        "rows": [i, j],
                        "position": p,
                        "values": [u, v],
                    }
                    if not clash:
                        event.update(keep=min(u, v), replace=max(u, v))
                    events.append(event)
        checks.append(
            {
                "dependency": di,
                "body_match_count": count,
                "violation_count": len(events),
                "satisfied": not events,
            }
        )
        result += events
    return result, checks


def chase(query, deps, literals):
    symbols = sorted(
        ["n:" + v for v in variables(query["body"])] + ["c:" + c for c in literals]
    )
    parent = {s: s for s in symbols}

    def find(s):
        while parent[s] != s:
            s = parent[s]
        return s

    facts = {
        fact_key({"relation": a["relation"], "values": [symbol(t) for t in a["terms"]]})
        for a in query["body"]
    }

    def snapshot():
        return {
            "domain": sorted({find(s) for s in symbols}),
            "facts": [as_fact(f) for f in sorted(facts)],
            "aliases": {s: find(s) for s in symbols},
            "head": [find("n:" + v) for v in query["head"]],
        }

    trace = [{"step": 0, "event": None, "state": snapshot()}]
    failure = None
    while True:
        events, checks = actions(deps, [as_fact(f) for f in sorted(facts)])
        if not events:
            break
        event = events[0]
        if event["kind"] == "add":
            facts.add(fact_key(event["fact"]))
        elif event["kind"] == "merge":
            parent[event["replace"]] = event["keep"]
            facts = {(r, tuple(find(v) for v in values)) for r, values in facts}
        else:
            failure = event
        trace.append({"step": len(trace), "event": event, "state": snapshot()})
        if failure:
            break
        if len(trace) > 380:
            raise ValueError("finite chase bound violated")
    _, checks = actions(deps, trace[-1]["state"]["facts"])
    return {
        "failed": failure is not None,
        "failure": failure,
        "trace": trace,
        "final_state": trace[-1]["state"],
        "dependency_checks": checks,
    }


def evaluate(q, state):
    rows = joins(q["body"], state["facts"])
    for row in rows:
        row["tuple"] = [row["binding"][h] for h in q["head"]]
    return {
        "derivations": rows,
        "answers": [list(t) for t in sorted({tuple(r["tuple"]) for r in rows})],
    }


def direction(source, target, deps, cs, sl, tl):
    c = chase(target, deps, cs)
    initial = c["trace"][0]["state"]
    baseline = initial["head"] in evaluate(source, initial)["answers"]
    state = c["final_state"]
    se = None if c["failed"] else evaluate(source, state)
    te = None if c["failed"] else evaluate(target, state)
    contained = c["failed"] or state["head"] in se["answers"]
    witness = None
    if contained and not c["failed"]:
        witness = next(
            i for i, r in enumerate(se["derivations"]) if r["tuple"] == state["head"]
        )
    return {
        "source": sl,
        "target": tl,
        "containment": tl + " ⊆Σ " + sl,
        "unconstrained_contained": baseline,
        "contained": contained,
        "reason": (
            "target-unsatisfiable"
            if c["failed"]
            else "mapped" if contained else "counterexample"
        ),
        "chase": c,
        "source_evaluation": se,
        "target_evaluation": te,
        "witness_derivation": witness,
        "counterexample_tuple": state["head"] if not contained else None,
    }


def summarize(d):
    return {
        "contained": d["contained"],
        "reason": d["reason"],
        "chase_steps": len(d["chase"]["trace"]) - 1,
        "final_fact_count": len(d["chase"]["final_state"]["facts"]),
    }


def analyze(request):
    d = validate(request)
    cs = all_constants(d)
    directions = [
        direction(d[src], d[dst], d["dependencies"], cs, src, dst)
        for src, dst in [("right", "left"), ("left", "right")]
    ]
    atlas = []
    for mask in range(1 << len(d["dependencies"])):
        ids = [i for i in range(len(d["dependencies"])) if mask >> i & 1]
        deps = [d["dependencies"][i] for i in ids]
        ds = [
            direction(d[src], d[dst], deps, cs, src, dst)
            for src, dst in [("right", "left"), ("left", "right")]
        ]
        atlas.append(
            {
                "mask": mask,
                "retained_dependencies": ids,
                "directions": [summarize(x) for x in ds],
                "set_equivalent": all(x["contained"] for x in ds),
                "minimal_support": [False, False],
                "minimum_support": [False, False],
            }
        )
    minima = []
    for di in range(2):
        successful = [a for a in atlas if a["directions"][di]["contained"]]
        n = min((len(a["retained_dependencies"]) for a in successful), default=None)
        minima.append(n)
        for a in successful:
            a["minimal_support"][di] = not any(
                b["mask"] != a["mask"] and b["mask"] & a["mask"] == b["mask"]
                for b in successful
            )
            a["minimum_support"][di] = len(a["retained_dependencies"]) == n
    return {
        "schema": "provlab-chase-v1",
        "input": d,
        "literal_constants": cs,
        "directions": directions,
        "set_equivalent": all(x["contained"] for x in directions),
        "minimum_support_sizes": minima,
        "dependency_atlas": atlas,
        "limits": LIMITS[:],
    }
