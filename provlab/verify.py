"""Independent active-domain valuation and Shannon probability replay.

Imports no join generator. Input validation/type comparison are shared plumbing.
"""

from itertools import product
from fractions import Fraction
from .input import validate, variables, equal, LIMITS


def replay(request):
    data = validate(request)
    relations = {r["name"]: r for r in data["relations"]}
    facts = [r for table in data["relations"] for r in table["rows"]]
    ids = [f["id"] for f in facts]
    domain = sorted(
        set(v for f in facts for v in f["values"])
        | set(
            t["const"]
            for body in data["query"]["branches"]
            for a in body
            for t in a["terms"]
            if "const" in t
        )
    )
    n = len(ids)
    tables = {
        r["name"]: {tuple(f["values"]): f for f in r["rows"]} for r in data["relations"]
    }
    probs = [Fraction(f["probability"]) for f in facts]
    head = data["query"]["head"]

    def assignments(body):
        vs = variables(body)
        for values in product(domain, repeat=len(vs)):
            binding = dict(zip(vs, values))
            used = []
            for atom in body:
                values = tuple(
                    binding[t["var"]] if "var" in t else t["const"]
                    for t in atom["terms"]
                )
                fact = tables[atom["relation"]].get(values)
                if fact is None:
                    break
                used.append(fact["id"])
            else:
                yield binding, used

    branches = []
    derivations = []
    for bi, body in enumerate(data["query"]["branches"]):
        stages = []
        for k in range(1, len(body) + 1):
            stages.append(
                {
                    "atom_index": k - 1,
                    "variables": variables(body[:k]),
                    "partials": [
                        {"binding": b, "tokens": used}
                        for b, used in assignments(body[:k])
                    ],
                }
            )
        branches.append({"branch": bi, "variables": variables(body), "stages": stages})
        for binding, used in assignments(body):
            exponents = [sum(t == ident for t in used) for ident in ids]
            copies = 1
            for token in used:
                copies *= facts[ids.index(token)]["multiplicity"]
            derivations.append(
                {
                    "branch": bi,
                    "binding": binding,
                    "output": [binding[h] for h in head],
                    "tokens": used,
                    "exponents": exponents,
                    "bag_weight": copies,
                }
            )
    outputs = []
    for values in sorted(set(tuple(d["output"]) for d in derivations)):
        selected = [
            i for i, d in enumerate(derivations) if tuple(d["output"]) == values
        ]
        terms = {}
        supports = []
        for i in selected:
            exponent = tuple(derivations[i]["exponents"])
            terms[exponent] = terms.get(exponent, 0) + 1
            support = frozenset(derivations[i]["tokens"])
            if support not in supports:
                supports.append(support)

        def support_mask(s):
            return sum(1 << i for i, t in enumerate(ids) if t in s)

        supports.sort(key=support_mask)
        minimal = [s for s in supports if not any(t < s for t in supports)]
        worlds = []
        truth = []
        # Direct re-query of each possible database, not evaluation of the generator's
        # polynomial nor trusting a claimed derivation support.
        for mask in range(1 << n):
            present = {ids[i] for i in range(n) if mask & (1 << i)}
            keys = []
            for bi, body in enumerate(data["query"]["branches"]):
                for binding, used in assignments(body):
                    if tuple(binding[h] for h in head) == values and all(
                        t in present for t in used
                    ):
                        keys.append((bi, binding))
            active = [
                i
                for i, d in enumerate(derivations)
                if (d["branch"], d["binding"]) in keys and i in selected
            ]
            holds = bool(keys)
            truth.append(holds)
            mass = Fraction(1)
            for i, p in enumerate(probs):
                mass *= p if ids[i] in present else 1 - p
            worlds.append(
                {
                    "mask": mask,
                    "present": [t for t in ids if t in present],
                    "derivation_indices": active,
                    "holds": holds,
                    "mass": str(mass),
                    "included_mass": str(mass if holds else Fraction(0)),
                }
            )

        def shannon(index, mask):
            if index == n:
                return Fraction(int(truth[mask]))
            return (1 - probs[index]) * shannon(index + 1, mask) + probs[
                index
            ] * shannon(index + 1, mask | (1 << index))

        probability = shannon(0, 0)
        arithmetic = Fraction(0)
        for exponent, coefficient in terms.items():
            value = Fraction(coefficient)
            for i, count in enumerate(exponent):
                for _ in range(count):
                    value *= probs[i]
            arithmetic += value
        outputs.append(
            {
                "tuple": list(values),
                "derivation_indices": selected,
                "terms": [
                    {"coefficient": terms[e], "exponents": list(e)}
                    for e in sorted(terms, reverse=True)
                ],
                "derivation_count": len(selected),
                "bag_multiplicity": sum(derivations[i]["bag_weight"] for i in selected),
                "used_tokens": [t for t in ids if any(t in s for s in supports)],
                "witnesses": [[t for t in ids if t in s] for s in supports],
                "minimal_witnesses": [[t for t in ids if t in s] for s in minimal],
                "worlds": worlds,
                "presence_probability": str(probability),
                "arithmetic_probability_substitution": str(arithmetic),
                "substitution_matches_here": arithmetic == probability,
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


def verify(report):
    if type(report) is not dict or "input" not in report:
        raise ValueError("certificate requires input")
    equal(replay(report["input"]), report)
    return True
