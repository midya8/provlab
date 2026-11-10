"""Sequential finite joins with exact natural-polynomial provenance."""

from collections import Counter
from fractions import Fraction as Q
from .input import validate, variables, LIMITS


def analyze(request):
    data = validate(request)
    rs = {r["name"]: r for r in data["relations"]}
    tokens = [row for r in data["relations"] for row in r["rows"]]
    ids = [r["id"] for r in tokens]
    m = len(ids)
    domain = sorted(
        {v for r in tokens for v in r["values"]}
        | {
            t["const"]
            for b in data["query"]["branches"]
            for a in b
            for t in a["terms"]
            if "const" in t
        }
    )
    head = data["query"]["head"]
    branches = []
    derivations = []
    for bi, body in enumerate(data["query"]["branches"]):
        partial = [{"binding": {}, "tokens": []}]
        stages = []
        for ai, a in enumerate(body):
            after = []
            for p in partial:
                for row in rs[a["relation"]]["rows"]:
                    binding = dict(p["binding"])
                    ok = True
                    for term, value in zip(a["terms"], row["values"]):
                        if "const" in term:
                            if term["const"] != value:
                                ok = False
                                break
                        else:
                            v = term["var"]
                            if v in binding and binding[v] != value:
                                ok = False
                                break
                            binding[v] = value
                    if ok:
                        after.append(
                            {"binding": binding, "tokens": p["tokens"] + [row["id"]]}
                        )
            vs = variables(body[: ai + 1])
            after.sort(
                key=lambda p: (
                    tuple(p["binding"][v] for v in vs),
                    tuple(ids.index(i) for i in p["tokens"]),
                )
            )
            stages.append({"atom_index": ai, "variables": vs, "partials": after})
            partial = after
        vs = variables(body)
        for p in partial:
            exp = [p["tokens"].count(i) for i in ids]
            derivations.append(
                {
                    "branch": bi,
                    "binding": {v: p["binding"][v] for v in vs},
                    "output": [p["binding"][h] for h in head],
                    "tokens": p["tokens"],
                    "exponents": exp,
                    "bag_weight": _product(
                        [tokens[i]["multiplicity"] ** e for i, e in enumerate(exp)]
                    ),
                }
            )
        branches.append({"branch": bi, "variables": vs, "stages": stages})
    outputs = []
    for output in sorted({tuple(d["output"]) for d in derivations}):
        ds = [i for i, d in enumerate(derivations) if tuple(d["output"]) == output]
        poly = Counter(tuple(derivations[i]["exponents"]) for i in ds)
        terms = [
            {"coefficient": poly[e], "exponents": list(e)}
            for e in sorted(poly, reverse=True)
        ]
        witnesses = sorted(
            {sum(1 << i for i, e in enumerate(t["exponents"]) if e) for t in terms}
        )
        minimal = [
            w for w in witnesses if not any(v != w and v & w == v for v in witnesses)
        ]
        prob = Q(0)
        worlds = []
        for mask in range(1 << m):
            active = [
                i
                for i in ds
                if all(
                    not e or mask >> j & 1
                    for j, e in enumerate(derivations[i]["exponents"])
                )
            ]
            weight = _product(
                [
                    Q(t["probability"]) if mask >> i & 1 else 1 - Q(t["probability"])
                    for i, t in enumerate(tokens)
                ]
            )
            holds = bool(active)
            if holds:
                prob += weight
            worlds.append(
                {
                    "mask": mask,
                    "present": [ids[i] for i in range(m) if mask >> i & 1],
                    "derivation_indices": active,
                    "holds": holds,
                    "mass": str(weight),
                    "included_mass": str(weight if holds else Q(0)),
                }
            )
        arithmetic = sum(
            Q(t["coefficient"])
            * _product(
                [Q(tokens[i]["probability"]) ** e for i, e in enumerate(t["exponents"])]
            )
            for t in terms
        )
        bag = sum(derivations[i]["bag_weight"] for i in ds)
        outputs.append(
            {
                "tuple": list(output),
                "derivation_indices": ds,
                "terms": terms,
                "derivation_count": len(ds),
                "bag_multiplicity": bag,
                "used_tokens": [
                    ids[i] for i in range(m) if any(t["exponents"][i] for t in terms)
                ],
                "witnesses": [
                    [ids[i] for i in range(m) if mask >> i & 1] for mask in witnesses
                ],
                "minimal_witnesses": [
                    [ids[i] for i in range(m) if mask >> i & 1] for mask in minimal
                ],
                "worlds": worlds,
                "presence_probability": str(prob),
                "arithmetic_probability_substitution": str(arithmetic),
                "substitution_matches_here": arithmetic == prob,
            }
        )
    return {
        "schema": "provlab-v1",
        "input": data,
        "domain": domain,
        "tokens": ids,
        "branches": branches,
        "derivations": derivations,
        "outputs": outputs,
        "limits": LIMITS[:],
    }


def _product(xs):
    result = 1
    for x in xs:
        result *= x
    return result
