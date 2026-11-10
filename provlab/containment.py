"""Reverse homomorphism atlases and canonical finite counterexamples."""

from itertools import product
from .containment_input import validate, variables, constants, LIMITS


def term_key(term):
    return ("v:" + term["var"]) if "var" in term else ("c:" + term["const"])


def decoded(key):
    return {"var": key[2:]} if key.startswith("v:") else {"const": key[2:]}


def atom_key(atom):
    return (atom["relation"], tuple(term_key(t) for t in atom["terms"]))


def maps(source, target, literals):
    vs = variables(source["body"])
    values = ["v:" + v for v in variables(target["body"])] + [
        "c:" + c for c in literals
    ]
    out = []
    for assignment in product(values, repeat=len(vs)):
        binding = dict(zip(vs, assignment))
        image = lambda t: binding[t["var"]] if "var" in t else "c:" + t["const"]
        head_image = [image({"var": v}) for v in source["head"]]
        preserved = head_image == ["v:" + v for v in target["head"]]
        checks = []
        for i, atom in enumerate(source["body"]):
            key = (atom["relation"], tuple(image(t) for t in atom["terms"]))
            matches = [j for j, a in enumerate(target["body"]) if atom_key(a) == key]
            checks.append(
                {
                    "source_atom": i,
                    "image": {
                        "relation": key[0],
                        "terms": [decoded(v) for v in key[1]],
                    },
                    "target_atoms": matches,
                    "matched": bool(matches),
                }
            )
        out.append(
            {
                "mapping": {v: decoded(binding[v]) for v in vs},
                "head_image": [decoded(v) for v in head_image],
                "head_preserved": preserved,
                "atom_checks": checks,
                "valid": preserved and all(c["matched"] for c in checks),
            }
        )
    return out


def canonical(query, literals):
    facts = []
    for ai, atom in enumerate(query["body"]):
        row = {
            "relation": atom["relation"],
            "values": [term_key(t) for t in atom["terms"]],
        }
        found = next(
            (
                f
                for f in facts
                if f["relation"] == row["relation"] and f["values"] == row["values"]
            ),
            None,
        )
        if found is None:
            row["source_atoms"] = [ai]
            facts.append(row)
        else:
            found["source_atoms"].append(ai)
    return {
        "domain": sorted(
            ["v:" + v for v in variables(query["body"])] + ["c:" + c for c in literals]
        ),
        "facts": facts,
        "frozen_head": ["v:" + v for v in query["head"]],
    }


def evaluate(query, database):
    partials = [({}, [])]
    for atom in query["body"]:
        following = []
        for binding, uses in partials:
            for fi, fact in enumerate(database["facts"]):
                if atom["relation"] != fact["relation"]:
                    continue
                b = dict(binding)
                valid = True
                for term, value in zip(atom["terms"], fact["values"]):
                    if "const" in term:
                        if value != "c:" + term["const"]:
                            valid = False
                            break
                    else:
                        if term["var"] in b and b[term["var"]] != value:
                            valid = False
                            break
                        b[term["var"]] = value
                if valid:
                    following.append((b, uses + [fi]))
        partials = following
    vs = variables(query["body"])
    partials.sort(key=lambda p: (tuple(p[0][v] for v in vs), p[1]))
    rows = []
    for binding, uses in partials:
        rows.append(
            {
                "binding": {v: binding[v] for v in vs},
                "tuple": [binding[h] for h in query["head"]],
                "fact_uses": uses,
                "exponents": [uses.count(i) for i in range(len(database["facts"]))],
            }
        )
    answers = []
    for output in sorted({tuple(r["tuple"]) for r in rows}):
        indices = [i for i, r in enumerate(rows) if tuple(r["tuple"]) == output]
        answers.append(
            {
                "tuple": list(output),
                "derivation_indices": indices,
                "set_present": True,
                "uniform_bag_multiplicity": len(indices) * 2 ** len(query["body"]),
            }
        )
    return {"derivations": rows, "answers": answers}


def direction(source, target, literals, source_label, target_label):
    candidates = maps(source, target, literals)
    success = [i for i, c in enumerate(candidates) if c["valid"]]
    database = canonical(target, literals)
    te = evaluate(target, database)
    se = evaluate(source, database)
    contained = bool(success)
    return {
        "source": source_label,
        "target": target_label,
        "containment": target_label + " ⊆ " + source_label,
        "map_direction": source_label + " → " + target_label,
        "candidates": candidates,
        "valid_candidate_indices": success,
        "mapping_count": len(success),
        "contained": contained,
        "canonical_database": database,
        "target_evaluation": te,
        "source_evaluation": se,
        "counterexample_tuple": None if contained else database["frozen_head"][:],
    }


def minimize(query, literals):
    atlas = []
    for mask in range(1 << len(query["body"])):
        kept = [i for i in range(len(query["body"])) if mask >> i & 1]
        body = [query["body"][i] for i in kept]
        missing = [h for h in query["head"] if h not in variables(body)]
        safe = bool(body) and not missing
        valid = []
        if safe:
            valid = [
                c["mapping"]
                for c in maps(query, {"head": query["head"], "body": body}, literals)
                if c["valid"]
            ]
        atlas.append(
            {
                "mask": mask,
                "retained_atoms": kept,
                "missing_head_variables": missing,
                "safe_nonempty": safe,
                "mapping_count": len(valid),
                "first_mapping": valid[0] if valid else None,
                "set_equivalent": bool(valid),
                "minimum": False,
            }
        )
    minimum = min(len(c["retained_atoms"]) for c in atlas if c["set_equivalent"])
    masks = []
    for c in atlas:
        c["minimum"] = c["set_equivalent"] and len(c["retained_atoms"]) == minimum
        if c["minimum"]:
            masks.append(c["mask"])
    return {"minimum_atom_count": minimum, "minimum_masks": masks, "atlas": atlas}


def analyze(request):
    data = validate(request)
    literals = constants([data["left"], data["right"]])
    lr = direction(data["right"], data["left"], literals, "right", "left")
    rl = direction(data["left"], data["right"], literals, "left", "right")
    return {
        "schema": "provlab-containment-v1",
        "input": data,
        "literal_constants": literals,
        "directions": [lr, rl],
        "set_equivalent": lr["contained"] and rl["contained"],
        "minimization": {
            "left": minimize(data["left"], literals),
            "right": minimize(data["right"], literals),
        },
        "limits": LIMITS[:],
    }
