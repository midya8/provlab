"""Original rule/key controls, including quotient heads and vacuous containment."""

import copy, random
from tools.containment_cases import a, q


def key(name, r, ps):
    return {"name": name, "kind": "key", "relation": r, "positions": ps}


def full(name, body, head):
    return {"name": name, "kind": "full", "body": body, "head": head}


def pair(left, right, deps, schema=None):
    return {
        "schema": schema or [{"name": "R", "arity": 2}, {"name": "S", "arity": 2}],
        "left": left,
        "right": right,
        "dependencies": deps,
    }


def controls():
    default = pair(
        q(["x", "y"], a("R", "k", "x"), a("R", "k", "y")),
        q(["u", "v"], a("R", "t", "u"), a("R", "t", "v"), a("S", "u", "v")),
        [
            key("one_value", "R", [0]),
            full("diagonal", [a("R", "t", "u")], a("S", "u", "u")),
            full("symmetry", [a("S", "u", "v")], a("S", "v", "u")),
        ],
    )
    cases = [
        (
            "Two assumptions, one rewrite",
            "A key merges the two output values. A full rule then supplies the diagonal S fact. Neither assumption alone proves the left-to-right rewrite.",
            default,
        )
    ]
    for name, why, ids in [
        (
            "No constraints",
            "The unchased database is a valid counterexample only when no extra constraints are selected.",
            [],
        ),
        (
            "Only the key",
            "The output values merge, but no S fact is forced. Equality alone is not the whole proof.",
            [0],
        ),
        (
            "Only the full rule",
            "Diagonal S facts appear, but the two output values need not be equal.",
            [1],
        ),
    ]:
        r = copy.deepcopy(default)
        r["dependencies"] = [r["dependencies"][i] for i in ids]
        cases.append((name, why, r))
    cases += [
        (
            "Literal clash is vacuity",
            "Distinct literal constants cannot merge. This target query has no answers on any database satisfying its key; a vacuous implication is labeled, not sold as a nonempty rewrite.",
            pair(
                q([], a("R", "@a", "@a"), a("R", "@a", "@b")),
                q([], a("S", "u", "u")),
                [key("one_value", "R", [0])],
            ),
        ),
        (
            "Output becomes a literal",
            "A key can identify a mergeable output symbol with a fixed literal. It must substitute in the output tuple too.",
            pair(
                q(["x"], a("R", "@a", "x"), a("R", "@a", "@b")),
                q(["u"], a("R", "@a", "u"), a("S", "u", "u")),
                [
                    key("one_value", "R", [0]),
                    full("diagonal", [a("R", "t", "u")], a("S", "u", "u")),
                ],
            ),
        ),
        (
            "Boolean output",
            "An empty output tuple asks whether the pattern exists. It is not a fabricated tuple when the source query fails.",
            pair(
                q([], a("R", "x", "y")),
                q([], a("S", "u", "u")),
                [full("range", [a("R", "x", "y")], a("S", "y", "y"))],
            ),
        ),
        (
            "Recursive but finite",
            "Full transitivity can add shortcuts without inventing symbols. This bounded chase is finite even with a recursive predicate.",
            pair(
                q(["x", "z"], a("R", "x", "y"), a("R", "y", "z")),
                q(["u", "v"], a("R", "u", "v")),
                [
                    full(
                        "transitive",
                        [a("R", "x", "y"), a("R", "y", "z")],
                        a("R", "x", "z"),
                    )
                ],
            ),
        ),
        (
            "New fact activates a key",
            "A full rule supplies a second R row. Only then does the key force equality; the order is visible in the trace.",
            pair(
                q(["x", "y"], a("R", "k", "x"), a("S", "k", "y")),
                q(["u", "v"], a("R", "t", "u"), a("S", "t", "v"), a("R", "t", "v")),
                [
                    full("copy", [a("S", "k", "y")], a("R", "k", "y")),
                    key("one_value", "R", [0]),
                ],
            ),
        ),
        (
            "Names are not identities",
            "The variable named a starts as n:a, distinct from the rigid literal c:a. A key may later merge them, but spelling alone cannot.",
            pair(
                q(["a"], a("R", "@a", "a")),
                q(["x"], a("R", "@a", "x"), a("S", "x", "x")),
                [full("diagonal", [a("R", "k", "x")], a("S", "x", "x"))],
            ),
        ),
        (
            "Ground facts, empty binding",
            "A rule whose body and head are constant-only has one empty variable binding. Literal constants are never fresh existential witnesses.",
            pair(
                q([], a("R", "@a", "@b")),
                q([], a("S", "@b", "@a")),
                [full("ground", [a("R", "@a", "@b")], a("S", "@b", "@a"))],
            ),
        ),
        (
            "A composite key is not a unary key",
            "Key positions[0,1] identify an entire binary row, so two distinct rows need not merge.",
            pair(
                q(["x", "y"], a("R", "k", "x"), a("R", "k", "y")),
                q(["u", "v"], a("R", "t", "u"), a("R", "t", "v"), a("S", "u", "v")),
                [
                    key("whole_row", "R", [0, 1]),
                    full("diagonal", [a("R", "k", "x")], a("S", "x", "x")),
                ],
            ),
        ),
    ]
    alternatives = copy.deepcopy(default)
    alternatives["dependencies"][2] = full(
        "direct", [a("R", "k", "x"), a("R", "k", "y")], a("S", "x", "y")
    )
    cases.append(
        (
            "Minimal is not minimum",
            "The direct rule alone suffices. The key plus diagonal rule is also inclusion-minimal, but it is not a smallest-cardinality support.",
            alternatives,
        )
    )
    cases.append(
        (
            "A rule forces a literal clash",
            "The initial facts do not violate the key. A full rule first adds a conflicting literal row; the resulting key clash proves target unsatisfiability.",
            pair(
                q([], a("R", "k", "@a"), a("S", "k", "x")),
                q([], a("S", "u", "u")),
                [
                    full("force_b", [a("S", "k", "x")], a("R", "k", "@b")),
                    key("one_value", "R", [0]),
                ],
            ),
        )
    )
    return [{"name": name, "why": why, "input": data} for name, why, data in cases]


def requests(n=80):
    rng = random.Random(97102)
    result = []
    for _ in range(n):
        schema = [
            {"name": "R", "arity": rng.choice([1, 2])},
            {"name": "S", "arity": rng.choice([1, 2])},
        ]
        heads = rng.randrange(3)
        queries = []
        for _ in range(2):
            while True:
                body = [
                    a(
                        r["name"],
                        *[
                            rng.choice(["x", "y", "z", "@a", "@b"])
                            for _ in range(r["arity"])
                        ]
                    )
                    for r in [rng.choice(schema) for _ in range(rng.randrange(1, 5))]
                ]
                vs = list(
                    dict.fromkeys(
                        t["var"] for atom in body for t in atom["terms"] if "var" in t
                    )
                )
                if len(vs) >= heads:
                    break
            queries.append(q(rng.sample(vs, heads), *body))
        deps = []
        for i in range(rng.randrange(4)):
            r = rng.choice(schema)
            if rng.random() < 0.4:
                deps.append(
                    key(
                        "d" + str(i),
                        r["name"],
                        rng.sample(
                            list(range(r["arity"])), rng.randrange(1, r["arity"] + 1)
                        ),
                    )
                )
            else:
                body = [
                    a(
                        r["name"],
                        *[
                            rng.choice(["x", "y", "z", "@a", "@b"])
                            for _ in range(r["arity"])
                        ]
                    )
                    for r in [rng.choice(schema) for _ in range(rng.randrange(1, 3))]
                ]
                vs = [t["var"] for atom in body for t in atom["terms"] if "var" in t]
                r = rng.choice(schema)
                deps.append(
                    full(
                        "d" + str(i),
                        body,
                        a(
                            r["name"],
                            *[rng.choice(vs + ["@a", "@b"]) for _ in range(r["arity"])]
                        ),
                    )
                )
        result.append(pair(*queries, deps, schema))
    return result


if __name__ == "__main__":
    import json
    from pathlib import Path

    Path("docs/chase-controls.json").write_text(json.dumps(controls(), indent=2) + "\n")
    Path("examples/chase-default.json").write_text(
        json.dumps(controls()[0]["input"], indent=2) + "\n"
    )
