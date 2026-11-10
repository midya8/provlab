"""Independent active-domain checker. Does not import the homomorphism engine."""

from itertools import product
from .containment_input import validate, LIMITS


def query_vars(q):
    return list(
        dict.fromkeys(t["var"] for a in q["body"] for t in a["terms"] if "var" in t)
    )


def key(t):
    return ("v:" + t["var"]) if "var" in t else ("c:" + t["const"])


def term(s):
    return {("var" if s[:2] == "v:" else "const"): s[2:]}


def database(q, cs):
    rows = []
    locations = {}
    for i, a in enumerate(q["body"]):
        k = (a["relation"], tuple(map(key, a["terms"])))
        if k not in locations:
            locations[k] = len(rows)
            rows.append({"relation": k[0], "values": list(k[1]), "source_atoms": []})
        rows[locations[k]]["source_atoms"].append(i)
    return {
        "domain": sorted(["v:" + v for v in query_vars(q)] + ["c:" + c for c in cs]),
        "facts": rows,
        "frozen_head": ["v:" + h for h in q["head"]],
    }


def ground(q, db):
    vs = query_vars(q)
    lookup = {(f["relation"], tuple(f["values"])): i for i, f in enumerate(db["facts"])}
    rows = []
    for values in product(db["domain"], repeat=len(vs)):
        valuation = dict(zip(vs, values))
        uses = []
        for a in q["body"]:
            row = tuple(
                valuation[t["var"]] if "var" in t else "c:" + t["const"]
                for t in a["terms"]
            )
            index = lookup.get((a["relation"], row))
            if index is None:
                break
            uses.append(index)
        else:
            rows.append(
                {
                    "binding": valuation,
                    "tuple": [valuation[h] for h in q["head"]],
                    "fact_uses": uses,
                    "exponents": [
                        sum(f == i for f in uses) for i in range(len(db["facts"]))
                    ],
                }
            )
    rows.sort(key=lambda r: (tuple(r["binding"][v] for v in vs), r["fact_uses"]))
    answers = []
    for output in sorted(set(tuple(r["tuple"]) for r in rows)):
        ids = [i for i, r in enumerate(rows) if r["tuple"] == list(output)]
        answers.append(
            {
                "tuple": list(output),
                "derivation_indices": ids,
                "set_present": True,
                "uniform_bag_multiplicity": sum(
                    2 ** len(rows[i]["fact_uses"]) for i in ids
                ),
            }
        )
    return {"derivations": rows, "answers": answers}


def candidates(q, target, cs):
    db = database(target, cs)
    vs = query_vars(q)
    result = []
    lookup = {}
    for i, a in enumerate(target["body"]):
        lookup.setdefault((a["relation"], tuple(map(key, a["terms"]))), []).append(i)
    # Preserve generator public ordering, but evaluate with direct ground lookup.
    domain = ["v:" + v for v in query_vars(target)] + ["c:" + c for c in cs]
    for vals in product(domain, repeat=len(vs)):
        v = dict(zip(vs, vals))
        head = [v[h] for h in q["head"]]
        atom_checks = []
        for i, a in enumerate(q["body"]):
            row = [v[t["var"]] if "var" in t else "c:" + t["const"] for t in a["terms"]]
            ids = lookup.get((a["relation"], tuple(row)), [])
            atom_checks.append(
                {
                    "source_atom": i,
                    "image": {"relation": a["relation"], "terms": list(map(term, row))},
                    "target_atoms": ids,
                    "matched": bool(ids),
                }
            )
        hp = head == db["frozen_head"]
        result.append(
            {
                "mapping": {k: term(x) for k, x in v.items()},
                "head_image": list(map(term, head)),
                "head_preserved": hp,
                "atom_checks": atom_checks,
                "valid": hp and all(x["matched"] for x in atom_checks),
            }
        )
    return result


def subset_atlas(q, cs):
    atlas = []
    for mask in range(2 ** len(q["body"])):
        ids = [i for i in range(len(q["body"])) if mask & (2**i)]
        sub = {"head": q["head"], "body": [q["body"][i] for i in ids]}
        missing = [h for h in q["head"] if h not in query_vars(sub)]
        safe = bool(ids) and not missing
        good = []
        equiv = False
        if safe:
            db = database(sub, cs)
            ev = ground(q, db)
            equiv = db["frozen_head"] in [a["tuple"] for a in ev["answers"]]
            good = [c["mapping"] for c in candidates(q, sub, cs) if c["valid"]]
            if equiv != bool(good):
                raise ValueError("internal ground/mapping mismatch")
        atlas.append(
            {
                "mask": mask,
                "retained_atoms": ids,
                "missing_head_variables": missing,
                "safe_nonempty": safe,
                "mapping_count": len(good),
                "first_mapping": good[0] if good else None,
                "set_equivalent": equiv,
                "minimum": False,
            }
        )
    n = min(len(a["retained_atoms"]) for a in atlas if a["set_equivalent"])
    ms = []
    for a in atlas:
        a["minimum"] = a["set_equivalent"] and len(a["retained_atoms"]) == n
        if a["minimum"]:
            ms.append(a["mask"])
    return {"minimum_atom_count": n, "minimum_masks": ms, "atlas": atlas}


def expected(request):
    data = validate(request)
    cs = sorted(
        {
            t["const"]
            for q in [data["left"], data["right"]]
            for a in q["body"]
            for t in a["terms"]
            if "const" in t
        }
    )
    directions = []
    for src, dst in [("right", "left"), ("left", "right")]:
        q = data[src]
        target = data[dst]
        db = database(target, cs)
        se = ground(q, db)
        te = ground(target, db)
        contained = db["frozen_head"] in [a["tuple"] for a in se["answers"]]
        cs_maps = candidates(q, target, cs)
        success = [i for i, c in enumerate(cs_maps) if c["valid"]]
        if contained != bool(success):
            raise ValueError("internal homomorphism theorem mismatch")
        directions.append(
            {
                "source": src,
                "target": dst,
                "containment": dst + " ⊆ " + src,
                "map_direction": src + " → " + dst,
                "candidates": cs_maps,
                "valid_candidate_indices": success,
                "mapping_count": len(success),
                "contained": contained,
                "canonical_database": db,
                "target_evaluation": te,
                "source_evaluation": se,
                "counterexample_tuple": None if contained else db["frozen_head"],
            }
        )
    return {
        "schema": "provlab-containment-v1",
        "input": data,
        "literal_constants": cs,
        "directions": directions,
        "set_equivalent": all(d["contained"] for d in directions),
        "minimization": {s: subset_atlas(data[s], cs) for s in ["left", "right"]},
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
        raise ValueError("comparison report missing input")
    if not exact(report, expected(report["input"])):
        raise ValueError(
            "comparison evidence does not match independent ground reconstruction"
        )
    return True
