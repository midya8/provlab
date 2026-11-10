"""Original bounded examples and deterministic comparison sampling."""

import random


def a(r, *terms):
    return {
        "relation": r,
        "terms": [{"const": t[1:]} if t.startswith("@") else {"var": t} for t in terms],
    }


def q(head, *body):
    return {"head": head, "body": list(body)}


def pair(left, right, schema=None):
    return {
        "schema": schema or [{"name": "R", "arity": 2}],
        "left": left,
        "right": right,
    }


def controls():
    cases = [
        (
            "Repeated evidence",
            "Set-equivalent is not bag-equivalent. Reusing one fact squares its multiplicity and token power.",
            pair(
                q(["x"], a("R", "x", "y"), a("R", "x", "y")), q(["u"], a("R", "u", "v"))
            ),
        ),
        (
            "Independent witness folds",
            "Two existential neighbors can use the same fact under set semantics. The fold merges variables, not output positions.",
            pair(
                q(["x"], a("R", "x", "y"), a("R", "x", "z")), q(["u"], a("R", "u", "v"))
            ),
        ),
        (
            "Longer path is stricter",
            "A three-edge path implies a two-edge prefix. The reverse mapping direction is the point.",
            pair(
                q(["x"], a("R", "x", "y"), a("R", "y", "z"), a("R", "z", "w")),
                q(["u"], a("R", "u", "v"), a("R", "v", "w")),
            ),
        ),
        (
            "Cycle versus path",
            "A directed triangle and a two-edge path are not equivalent. Inspect the failing direction and frozen counterexample.",
            pair(
                q(["x"], a("R", "x", "y"), a("R", "y", "z"), a("R", "z", "x")),
                q(["u"], a("R", "u", "v"), a("R", "v", "w")),
            ),
        ),
        (
            "Output order is binding",
            "Body shape alone is not enough. Swapping the two distinguished output positions changes the query.",
            pair(q(["x", "y"], a("R", "x", "y")), q(["v", "u"], a("R", "u", "v"))),
        ),
        (
            "A fixed literal",
            "The literal a is not a fresh variable. A required a-neighbor is stricter than any neighbor.",
            pair(q(["x"], a("R", "x", "@a")), q(["u"], a("R", "u", "v"))),
        ),
        (
            "Different literals",
            "Constants stay fixed even when a second literal is absent from the canonical facts.",
            pair(q(["x"], a("R", "x", "@a")), q(["u"], a("R", "u", "@b"))),
        ),
        (
            "Boolean head",
            "An empty ordered head asks only whether the pattern exists. A loop can witness both edges of a two-cycle.",
            pair(q([], a("R", "x", "x")), q([], a("R", "u", "v"), a("R", "v", "u"))),
        ),
        (
            "Nontrivial minimum",
            "A separate edge can fold into an existing length-two path. The complete atom-subset atlas exposes exactly which edge can be removed.",
            pair(
                q(["x"], a("R", "x", "y"), a("R", "x", "z"), a("R", "z", "w")),
                q(["u"], a("R", "u", "v"), a("R", "v", "w")),
            ),
        ),
        (
            "Relation names matter",
            "The same edge shape does not let R satisfy an S atom.",
            pair(
                q(["x"], a("R", "x", "y")),
                q(["u"], a("S", "u", "v")),
                [{"name": "R", "arity": 2}, {"name": "S", "arity": 2}],
            ),
        ),
        (
            "Ground Boolean atom",
            "A constant-only body has no variables to guess. The empty mapping is a genuine candidate.",
            pair(q([], a("R", "@a", "@a")), q([], a("R", "x", "x"))),
        ),
        (
            "Ternary projection",
            "Projection and repeated positions are enforced on arity-three atoms too.",
            pair(
                q(["x"], a("T", "x", "y", "y"), a("T", "x", "z", "z")),
                q(["u"], a("T", "u", "v", "v")),
                [{"name": "T", "arity": 3}],
            ),
        ),
    ]
    return [{"name": name, "why": why, "input": data} for name, why, data in cases]


def requests(n=100):
    rng = random.Random(641203)
    out = []
    for i in range(n):
        schema = [
            {"name": "R", "arity": rng.choice([1, 2, 3])},
            {"name": "S", "arity": rng.choice([1, 2])},
        ]
        queries = []
        heads = rng.choice([0, 1, 2])
        for _ in range(2):
            while True:
                body = []
                for _ in range(rng.randrange(1, 5)):
                    r = rng.choice(schema)
                    body.append(
                        a(
                            r["name"],
                            *[
                                rng.choice(["x", "y", "z", "w", "@a", "@b"])
                                for _ in range(r["arity"])
                            ]
                        )
                    )
                vs = list(
                    dict.fromkeys(
                        t["var"] for atom in body for t in atom["terms"] if "var" in t
                    )
                )
                if len(vs) >= heads:
                    break
            queries.append(q(rng.sample(vs, heads), *body))
        out.append(pair(*queries, schema))
    return out


if __name__ == "__main__":
    import json
    from pathlib import Path

    Path("docs/containment-controls.json").write_text(
        json.dumps(controls(), indent=2) + "\n"
    )
