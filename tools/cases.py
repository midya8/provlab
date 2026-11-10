"""Stable seeded safe UCQs over bounded ordinary relations."""

import itertools, random
from .make_controls import model, R, A, V, C


def requests(count=150):
    rng = random.Random(1042)
    out = []
    values = ["a", "b", "c"]
    pairs = list(itertools.product(values, repeat=2))
    for k in range(count):
        rows = rng.sample(pairs, rng.randrange(7))
        relations = [
            R(
                "E",
                2,
                [
                    (
                        "p" + str(i),
                        list(v),
                        rng.randrange(4),
                        rng.choice(["0", "1/4", "1/2", "2/3", "1"]),
                    )
                    for i, v in enumerate(rows)
                ],
            )
        ]
        branches = []
        for _ in range(rng.randrange(1, 5)):
            body = []
            for j in range(rng.randrange(1, 4)):
                # x occurs in every branch; remaining variables can change by atom.
                body.append(
                    A(
                        "E",
                        V("x") if j == 0 else rng.choice([V("x"), V("y"), C("a")]),
                        rng.choice([V("x"), V("y"), V("z"), C("b")]),
                    )
                )
            branches.append(body)
        out.append(model(relations, [] if k % 7 == 0 else ["x"], branches))
    return out
