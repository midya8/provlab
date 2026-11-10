"""Actual SQLite joins/bag copies and SymPy polynomial expansion references.

SQLite receives bound parameters for constants. Schema/aliases are generated,
not user identifiers. SymPy receives Symbol objects, never parsed expressions.
"""

import itertools, json, sqlite3, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy
from provlab import analyze
from provlab.input import validate
from tools.make_controls import controls
from tools.cases import requests


def sqlite_result(request, present=None, bag=False, provenance=False):
    d = validate(request)
    con = sqlite3.connect(":memory:")
    relations = {r["name"]: i for i, r in enumerate(d["relations"])}
    for i, r in enumerate(d["relations"]):
        con.execute(
            "CREATE TABLE t"
            + str(i)
            + "("
            + ",".join("c" + str(j) + " TEXT" for j in range(r["arity"]))
            + ",token TEXT)"
        )
        for row in r["rows"]:
            if present is not None and row["id"] not in present:
                continue
            for _ in range(row["multiplicity"] if bag else 1):
                con.execute(
                    "INSERT INTO t"
                    + str(i)
                    + " VALUES ("
                    + ",".join("?" for _ in row["values"] + [row["id"]])
                    + ")",
                    row["values"] + [row["id"]],
                )
    statements = []
    params = []
    for body in d["query"]["branches"]:
        seen = {}
        conditions = []
        tables = []
        for ai, atom in enumerate(body):
            alias = "a" + str(ai)
            tables.append("t" + str(relations[atom["relation"]]) + " " + alias)
            for j, t in enumerate(atom["terms"]):
                col = alias + ".c" + str(j)
                if "const" in t:
                    conditions.append(col + "=?")
                    params.append(t["const"])
                elif t["var"] in seen:
                    conditions.append(col + "=" + seen[t["var"]])
                else:
                    seen[t["var"]] = col
        select = ",".join(seen[h] for h in d["query"]["head"]) or "1"
        if provenance:
            select += "," + ",".join(
                ["a" + str(i) + ".token" for i in range(len(body))]
                + ["NULL"] * (3 - len(body))
            )
        statements.append(
            "SELECT "
            + select
            + " FROM "
            + ",".join(tables)
            + (" WHERE " + " AND ".join(conditions) if conditions else "")
        )
    sql = " UNION ALL ".join(statements)
    rows = con.execute(sql, params).fetchall()
    con.close()
    if provenance:
        h = max(1, len(d["query"]["head"]))
        return [
            (
                tuple(row[:h]) if d["query"]["head"] else (),
                [t for t in row[h:] if t is not None],
            )
            for row in rows
        ]
    return Counter(tuple(row) if d["query"]["head"] else () for row in rows)


def reference(request):
    r = analyze(request)
    ids = r["tokens"]
    symbols = [sympy.Symbol(t) for t in ids]
    facts = [f for rel in r["input"]["relations"] for f in rel["rows"]]
    bags = sqlite_result(request, bag=True)
    sql_provenance = sqlite_result(request, provenance=True)
    plain = sqlite_result(request)
    symchecks = 0
    for o in r["outputs"]:
        expression = 0
        for output, used in sql_provenance:
            if output != tuple(o["tuple"]):
                continue
            term = 1
            for t in used:
                term *= symbols[ids.index(t)]
            expression += term
        assert plain[tuple(o["tuple"])] == o["derivation_count"]
        polynomial = sympy.Poly(sympy.expand(expression), *symbols, domain=sympy.ZZ)
        actual = [
            {"coefficient": int(c), "exponents": list(e)} for e, c in polynomial.terms()
        ]
        assert actual == o["terms"]
        symchecks += 1
        assert bags[tuple(o["tuple"])] == o["bag_multiplicity"]
    for mask in range(1 << len(ids)):
        visible = sqlite_result(
            request, present={t for i, t in enumerate(ids) if mask >> i & 1}
        )
        for o in r["outputs"]:
            assert bool(visible[tuple(o["tuple"])]) == o["worlds"][mask]["holds"]
    assert set(bags).issubset({tuple(o["tuple"]) for o in r["outputs"]})
    return len(r["outputs"]), 1 << len(ids)


def main():
    cases = [c["input"] for c in controls()] + requests(150)
    outputs = worlds = 0
    for request in cases:
        a, b = reference(request)
        outputs += a
        worlds += b
    print(
        json.dumps(
            {
                "requests": len(cases),
                "sqlite_world_queries": worlds,
                "sqlite_bag_queries": len(cases),
                "sympy_polynomials": outputs,
                "sympy_version": sympy.__version__,
                "sqlite_version": sqlite3.sqlite_version,
            }
        )
    )


if __name__ == "__main__":
    main()
