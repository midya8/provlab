"""Independent Cartesian grounding and flat equality-substitution replay.

This module never imports chase.py. It reconstructs every trace field and also
checks terminal head membership directly, not a reported containment Boolean.
"""

from itertools import product
from .chase_input import validate, all_constants, LIMITS


def vars_in(body):
    return list(dict.fromkeys(t["var"] for a in body for t in a["terms"] if "var" in t))


def term(t):
    return "n:" + t["var"] if "var" in t else "c:" + t["const"]


def rowkey(f):
    return (f["relation"], tuple(f["values"]))


def rows(keys):
    return [{"relation": r, "values": list(v)} for r, v in sorted(keys)]


def ground(body, state):
    vs = vars_in(body)
    lookup = {rowkey(f): i for i, f in enumerate(state["facts"])}
    out = []
    for assignment in product(state["domain"], repeat=len(vs)):
        v = dict(zip(vs, assignment))
        matches = []
        for atom in body:
            value = tuple(
                v[t["var"]] if "var" in t else "c:" + t["const"] for t in atom["terms"]
            )
            i = lookup.get((atom["relation"], value))
            if i is None:
                break
            matches.append(i)
        else:
            out.append({"binding": v, "rows": matches})
    return out


def obligations(deps, state):
    events = []
    checks = []
    facts = state["facts"]
    present = {rowkey(f) for f in facts}
    for di, d in enumerate(deps):
        matches = 0
        es = []
        if d["kind"] == "full":
            valuations = ground(d["body"], state)
            matches = len(valuations)
            for valuation in valuations:
                v = valuation["binding"]
                head = d["head"]
                f = {
                    "relation": head["relation"],
                    "values": [
                        v[t["var"]] if "var" in t else "c:" + t["const"]
                        for t in head["terms"]
                    ],
                }
                if rowkey(f) not in present:
                    es.append(
                        {
                            "dependency": di,
                            "kind": "add",
                            "binding": v,
                            "premise_rows": valuation["rows"],
                            "fact": f,
                        }
                    )
        else:
            for i in range(len(facts)):
                a = facts[i]
                if a["relation"] != d["relation"]:
                    continue
                for j in range(i + 1, len(facts)):
                    b = facts[j]
                    if b["relation"] != d["relation"] or tuple(
                        a["values"][p] for p in d["positions"]
                    ) != tuple(b["values"][p] for p in d["positions"]):
                        continue
                    matches += 1
                    for p in range(len(a["values"])):
                        u = a["values"][p]
                        v = b["values"][p]
                        if u == v:
                            continue
                        is_clash = u[:2] == "c:" and v[:2] == "c:"
                        e = {
                            "dependency": di,
                            "kind": "clash" if is_clash else "merge",
                            "rows": [i, j],
                            "position": p,
                            "values": [u, v],
                        }
                        if not is_clash:
                            e["keep"], e["replace"] = sorted([u, v])
                        es.append(e)
        events += es
        checks.append(
            {
                "dependency": di,
                "body_match_count": matches,
                "violation_count": len(es),
                "satisfied": len(es) == 0,
            }
        )
    return events, checks


def replay(q, deps, cs):
    symbols = sorted(["n:" + v for v in vars_in(q["body"])] + ["c:" + c for c in cs])
    aliases = {s: s for s in symbols}
    facts = {
        rowkey({"relation": a["relation"], "values": list(map(term, a["terms"]))})
        for a in q["body"]
    }

    def snap():
        return {
            "domain": sorted(set(aliases.values())),
            "facts": rows(facts),
            "aliases": dict(aliases),
            "head": [aliases["n:" + v] for v in q["head"]],
        }

    state = snap()
    trace = [{"step": 0, "event": None, "state": state}]
    failure = None
    while True:
        events, checks = obligations(deps, state)
        if not events:
            break
        e = events[0]
        if e["kind"] == "add":
            facts.add(rowkey(e["fact"]))
        elif e["kind"] == "merge":
            change = lambda x: e["keep"] if x == e["replace"] else x
            aliases = {s: change(v) for s, v in aliases.items()}
            facts = {(r, tuple(map(change, values))) for r, values in facts}
        else:
            failure = e
        state = snap()
        trace.append({"step": len(trace), "event": e, "state": state})
        if failure:
            break
        if len(trace) > 380:
            raise ValueError("independent finite chase bound violated")
    _, checks = obligations(deps, state)
    return {
        "failed": failure is not None,
        "failure": failure,
        "trace": trace,
        "final_state": state,
        "dependency_checks": checks,
    }


def evaluate(q, state):
    derived = ground(q["body"], state)
    for v in derived:
        v["tuple"] = [v["binding"][h] for h in q["head"]]
    return {
        "derivations": derived,
        "answers": [list(t) for t in sorted(set(tuple(v["tuple"]) for v in derived))],
    }


def relation(data, src, dst, deps, cs):
    c = replay(data[dst], deps, cs)
    initial = c["trace"][0]["state"]
    state = c["final_state"]
    base = initial["head"] in evaluate(data[src], initial)["answers"]
    source = None if c["failed"] else evaluate(data[src], state)
    target = None if c["failed"] else evaluate(data[dst], state)
    found = (
        []
        if c["failed"]
        else [
            i
            for i, row in enumerate(source["derivations"])
            if row["tuple"] == state["head"]
        ]
    )
    contained = c["failed"] or bool(found)
    return {
        "source": src,
        "target": dst,
        "containment": dst + " ⊆Σ " + src,
        "unconstrained_contained": base,
        "contained": contained,
        "reason": (
            "target-unsatisfiable"
            if c["failed"]
            else "mapped" if found else "counterexample"
        ),
        "chase": c,
        "source_evaluation": source,
        "target_evaluation": target,
        "witness_derivation": found[0] if found else None,
        "counterexample_tuple": None if contained else state["head"],
    }


def expected(request):
    data = validate(request)
    cs = all_constants(data)
    pairs = [("right", "left"), ("left", "right")]
    ds = [relation(data, s, t, data["dependencies"], cs) for s, t in pairs]
    atlas = []
    for mask in range(2 ** len(data["dependencies"])):
        ids = [i for i in range(len(data["dependencies"])) if (mask // 2**i) % 2]
        chosen = [data["dependencies"][i] for i in ids]
        directions = [relation(data, s, t, chosen, cs) for s, t in pairs]
        summary = [
            {
                "contained": d["contained"],
                "reason": d["reason"],
                "chase_steps": len(d["chase"]["trace"]) - 1,
                "final_fact_count": len(d["chase"]["final_state"]["facts"]),
            }
            for d in directions
        ]
        atlas.append(
            {
                "mask": mask,
                "retained_dependencies": ids,
                "directions": summary,
                "set_equivalent": all(x["contained"] for x in summary),
                "minimal_support": [False, False],
                "minimum_support": [False, False],
            }
        )
    mins = []
    for di in range(2):
        supports = [row for row in atlas if row["directions"][di]["contained"]]
        n = min((len(row["retained_dependencies"]) for row in supports), default=None)
        mins.append(n)
        for row in supports:
            ids = set(row["retained_dependencies"])
            row["minimal_support"][di] = not any(
                set(other["retained_dependencies"]) < ids for other in supports
            )
            row["minimum_support"][di] = len(ids) == n
    return {
        "schema": "provlab-chase-v1",
        "input": data,
        "literal_constants": cs,
        "directions": ds,
        "set_equivalent": all(x["contained"] for x in ds),
        "minimum_support_sizes": mins,
        "dependency_atlas": atlas,
        "limits": LIMITS[:],
    }


def exact(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    return a == b


def verify(report):
    if type(report) is not dict or "input" not in report:
        raise ValueError("missing chase report input")
    if not exact(report, expected(report["input"])):
        raise ValueError(
            "chase evidence does not match independent ground reconstruction"
        )
    return True
