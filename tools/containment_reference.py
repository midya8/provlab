"""Actual SQLite SELECT DISTINCT/ALL and token-carrying joins plus SymPy.

No user strings enter SQL syntax. Generated schema aliases; bound literals.
Independent references use emitted canonical DBs and queries, not homomorphism results.
"""

import collections, itertools, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy
from provlab.containment import analyze
from provlab.containment_verify import verify
from tools.containment_cases import controls, requests


def sql(query, db, schema, mode):
    con = sqlite3.connect(":memory:")
    relations = {r["name"]: i for i, r in enumerate(schema)}
    for r in schema:
        name = "t" + str(relations[r["name"]])
        con.execute(
            "CREATE TABLE "
            + name
            + "("
            + ",".join("c" + str(i) + " TEXT" for i in range(r["arity"]))
            + ", token TEXT)"
        )
        for fi, fact in enumerate(db["facts"]):
            if fact["relation"] != r["name"]:
                continue
            for _ in range(2 if mode == "bag" else 1):
                con.execute(
                    "INSERT INTO "
                    + name
                    + " VALUES("
                    + ",".join("?" for _ in range(r["arity"] + 1))
                    + ")",
                    fact["values"] + ["f" + str(fi)],
                )
    aliases = []
    variables = {}
    where = []
    params = []
    for ai, atom in enumerate(query["body"]):
        alias = "a" + str(ai)
        aliases.append("t" + str(relations[atom["relation"]]) + " " + alias)
        for ti, t in enumerate(atom["terms"]):
            col = alias + ".c" + str(ti)
            if "const" in t:
                where.append(col + " = ?")
                params.append("c:" + t["const"])
            elif t["var"] in variables:
                where.append(col + " = " + variables[t["var"]])
            else:
                variables[t["var"]] = col
    selections = [variables[h] for h in query["head"]]
    if mode == "tokens":
        selections += ["a" + str(i) + ".token" for i in range(len(query["body"]))]
    statement = (
        "SELECT "
        + ("DISTINCT " if mode == "set" else "")
        + (",".join(selections) if selections else "1")
        + " FROM "
        + ",".join(aliases)
        + (" WHERE " + " AND ".join(where) if where else "")
    )
    rows = con.execute(statement, params).fetchall()
    con.close()
    if not selections:
        rows = [() for _ in rows]
    return rows


def run(n=100):
    num = 0
    poly_count = 0
    for request in [c["input"] for c in controls()] + requests(n):
        report = analyze(request)
        verify(report)
        for direction in report["directions"]:
            db = direction["canonical_database"]
            symbols = [sympy.Symbol("f" + str(i)) for i in range(len(db["facts"]))]
            for label, field in [
                (direction["target"], "target_evaluation"),
                (direction["source"], "source_evaluation"),
            ]:
                query = request[label]
                evaluation = direction[field]
                expected = {tuple(a["tuple"]): a for a in evaluation["answers"]}
                assert set(sql(query, db, request["schema"], "set")) == set(expected)
                assert collections.Counter(
                    sql(query, db, request["schema"], "bag")
                ) == collections.Counter(
                    {t: a["uniform_bag_multiplicity"] for t, a in expected.items()}
                )
                token_rows = sql(query, db, request["schema"], "tokens")
                actual = {t: 0 for t in expected}
                h = len(query["head"])
                for row in token_rows:
                    output = tuple(row[:h])
                    term = sympy.prod(sympy.Symbol(tok) for tok in row[h:])
                    actual[output] += term
                for output in expected:
                    native = sum(
                        sympy.prod(s**e for s, e in zip(symbols, d["exponents"]))
                        for d in evaluation["derivations"]
                        if tuple(d["tuple"]) == output
                    )
                    assert sympy.expand(actual[output] - native) == 0
                    poly_count += 1
                num += 3
    print(
        json.dumps(
            {
                "sqlite_version": sqlite3.sqlite_version,
                "sympy_version": sympy.__version__,
                "requests": n + len(controls()),
                "sqlite_queries": num,
                "sqlite_token_polynomials": poly_count,
            }
        )
    )


if __name__ == "__main__":
    run()
