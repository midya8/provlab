"""Original tiny databases and safe positive-query counterexamples."""

import json
from pathlib import Path


def V(x):
    return {"var": x}


def C(x):
    return {"const": x}


def A(r, *ts):
    return {"relation": r, "terms": list(ts)}


def R(name, arity, rows):
    return {
        "name": name,
        "arity": arity,
        "rows": [
            {"id": i, "values": v, "multiplicity": m, "probability": p}
            for i, v, m, p in rows
        ],
    }


def model(relations, head, branches):
    return {"relations": relations, "query": {"head": head, "branches": branches}}


def controls():
    r = R("R", 1, [("p", ["amy"], 2, "1/2")])
    s = R("S", 1, [("q", ["amy"], 3, "1/4")])
    x = V("x")
    y = V("y")
    z = V("z")
    return [
        {
            "id": "reuse",
            "title": "Reused is not independent",
            "why": "The same base token is used twice in one derivation. Its polynomial keeps p², but its Boolean event is still p. Presence probability is 1/2, not the ordinary polynomial substitution 3/8. Bag multiplicity at p=2, q=3 is 10.",
            "input": model(
                [r, s], ["x"], [[A("R", x), A("R", x)], [A("R", x), A("S", x)]]
            ),
        },
        {
            "id": "duplicate-branches",
            "title": "Same answers, different multiplicity",
            "why": "Repeating a union-all branch doubles how-provenance and bag multiplicity. It does not turn the same existence event into two independent chances.",
            "input": model([r], ["x"], [[A("R", x)], [A("R", x)]]),
        },
        {
            "id": "overlap",
            "title": "Two routes can share one fact",
            "why": "The two witnesses share p. Their events overlap; adding the route probabilities double-counts the world containing all three facts.",
            "input": model(
                [
                    r,
                    R("S", 1, [("q", ["amy"], 1, "1/2")]),
                    R("T", 1, [("r", ["amy"], 1, "1/2")]),
                ],
                ["x"],
                [[A("R", x), A("S", x)], [A("R", x), A("T", x)]],
            ),
        },
        {
            "id": "disjoint-tokens",
            "title": "Independent routes still overlap as events",
            "why": "Two distinct independent input events can both occur. The probability of their union is not the sum of their probabilities. Distinct witness sets need not be mutually exclusive.",
            "input": model([r, s], ["x"], [[A("R", x)], [A("S", x)]]),
        },
        {
            "id": "projection",
            "title": "Projection preserves alternative derivations",
            "why": "Two source rows project to the same output. The polynomial records both tokens, and each possible world shows whether at least one survives.",
            "input": model(
                [
                    R(
                        "Edge",
                        2,
                        [
                            ("p", ["amy", "bob"], 1, "1/2"),
                            ("q", ["amy", "cy"], 2, "1/3"),
                        ],
                    )
                ],
                ["x"],
                [[A("Edge", x, y)]],
            ),
        },
        {
            "id": "join-chain",
            "title": "A shared variable is a real join constraint",
            "why": "Only compatible intermediate values join. A Cartesian product would invent unsupported output pairs. Repeated output pairs still collect every valid route.",
            "input": model(
                [
                    R(
                        "Edge",
                        2,
                        [
                            ("p", ["amy", "bob"], 1, "1/2"),
                            ("q", ["bob", "cy"], 2, "1/2"),
                            ("r", ["amy", "cy"], 1, "1/3"),
                            ("s", ["cy", "cy"], 1, "1/4"),
                        ],
                    )
                ],
                ["x", "z"],
                [[A("Edge", x, y), A("Edge", y, z)]],
            ),
        },
        {
            "id": "repeated-variable",
            "title": "One variable cannot take two values in one atom",
            "why": "Edge(x,x) selects only diagonal rows. A variable repeated within an atom is an equality constraint, not a fresh wildcard.",
            "input": model(
                [
                    R(
                        "Edge",
                        2,
                        [
                            ("p", ["amy", "amy"], 1, "1/2"),
                            ("q", ["amy", "bob"], 2, "1/3"),
                            ("r", ["bob", "bob"], 3, "1"),
                        ],
                    )
                ],
                ["x"],
                [[A("Edge", x, x)]],
            ),
        },
        {
            "id": "constant-filter",
            "title": "Constants and variable names are different terms",
            "why": "The literal bob is fixed by a const term. A var term named bob would range over the active domain. Tagged terms avoid silently changing the query.",
            "input": model(
                [
                    R(
                        "Edge",
                        2,
                        [
                            ("p", ["amy", "bob"], 1, "1/2"),
                            ("q", ["amy", "cy"], 1, "1/2"),
                            ("r", ["cy", "bob"], 1, "0"),
                        ],
                    )
                ],
                ["x"],
                [[A("Edge", x, C("bob"))]],
            ),
        },
        {
            "id": "empty-answer",
            "title": "A missing witness gives no result tuple",
            "why": "The join requires a shared value, but no shared value exists. The empty result is explicit, not a zero-probability answer invented by projection.",
            "input": model(
                [r, R("S", 1, [("q", ["bob"], 1, "1/2")])],
                ["x"],
                [[A("R", x), A("S", x)]],
            ),
        },
        {
            "id": "boolean-head",
            "title": "Existence can have an empty output tuple",
            "why": "A safe Boolean query has a zero-column head. Its unit tuple () collects every matching binding. An empty head is not an empty conjunction.",
            "input": model(
                [R("R", 1, [("p", ["amy"], 1, "1/2"), ("q", ["bob"], 1, "1/3")])],
                [],
                [[A("R", x)]],
            ),
        },
        {
            "id": "zero-multiplicity",
            "title": "Bag zero is not probabilistic impossibility",
            "why": "Multiplicity0 and probability 1/2 describe separate interpretations. The bag answer has multiplicity 0 while its possible-world existence probability is 1/2. Neither field overwrites the other.",
            "input": model(
                [R("R", 1, [("p", ["amy"], 0, "1/2")])], ["x"], [[A("R", x)]]
            ),
        },
        {
            "id": "zero-one-worlds",
            "title": "Impossible worlds remain in the certificate",
            "why": "Base probabilities 0 and 1 give some worlds zero mass, but all four masks remain visible. Symbolic derivability, positive world mass and answer probability are separate facts.",
            "input": model(
                [
                    R("R", 1, [("p", ["amy"], 1, "0")]),
                    R("S", 1, [("q", ["amy"], 1, "1")]),
                ],
                ["x"],
                [[A("R", x)], [A("S", x)]],
            ),
        },
        {
            "id": "triple-reuse",
            "title": "Three uses still describe one event",
            "why": "A triple self-join preserves p³ in how-provenance and p-multiplicity cubed in bag semantics. Existence still asks whether p is present just once.",
            "input": model([r], ["x"], [[A("R", x), A("R", x), A("R", x)]]),
        },
        {
            "id": "empty-relation",
            "title": "A declared relation can have no tuples",
            "why": "There are no active values or derivations. The single empty possible database is implicit in the input, while no output tuple is fabricated for the failed Boolean query.",
            "input": model([R("R", 1, [])], [], [[A("R", x)]]),
        },
    ]


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    (root / "docs/controls.json").write_text(json.dumps(controls(), indent=2) + "\n")
    (root / "examples/reuse.json").write_text(
        json.dumps(controls()[0]["input"], indent=2) + "\n"
    )
