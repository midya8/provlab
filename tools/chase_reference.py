"""Actual SQLite query/dependency probes and exhaustive two-value models.

SQL WHERE clauses independently encode variable equality and literal constraints.
No generator joins, chase events or evaluator is used to check model semantics.
"""

import itertools, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provlab.chase import analyze
from tools.chase_cases import controls, requests


def sql(body, head=()):
    refs = {}
    clauses = []
    args = []
    tables = []
    for i, a in enumerate(body):
        alias = "a" + str(i)
        tables.append('"' + a["relation"] + '" ' + alias)
        for j, t in enumerate(a["terms"]):
            col = alias + ".c" + str(j)
            if "const" in t:
                clauses.append(col + "=?")
                args.append("c:" + t["const"])
            elif t["var"] in refs:
                clauses.append(col + "=" + refs[t["var"]])
            else:
                refs[t["var"]] = col
    projection = ",".join(refs[v] for v in head) if head else "1"
    return (
        "SELECT DISTINCT "
        + projection
        + " FROM "
        + ",".join(tables)
        + (" WHERE " + " AND ".join(clauses) if clauses else ""),
        args,
        refs,
    )


def answers(db, q):
    query, args, _ = sql(q["body"], q["head"])
    result = db.execute(query, args).fetchall()
    return set(result) if q["head"] else {() for _ in result}


def valid(db, deps):
    for d in deps:
        if d["kind"] == "key":
            arity = len(
                db.execute('PRAGMA table_info("' + d["relation"] + '")').fetchall()
            )
            on = " AND ".join("a.c" + str(p) + "=b.c" + str(p) for p in d["positions"])
            different = " OR ".join(
                "a.c" + str(p) + "<>b.c" + str(p) for p in range(arity)
            )
            statement = (
                'SELECT 1 FROM "'
                + d["relation"]
                + '" a JOIN "'
                + d["relation"]
                + '" b ON '
                + on
                + " WHERE "
                + different
                + " LIMIT 1"
            )
            if db.execute(statement).fetchone():
                return False
        else:
            query, args, refs = sql(d["body"])
            conditions = []
            for p, t in enumerate(d["head"]["terms"]):
                rhs = "?" if "const" in t else refs[t["var"]]
                conditions.append("h.c" + str(p) + "=" + rhs)
                if "const" in t:
                    args.append("c:" + t["const"])
            absent = (
                'NOT EXISTS(SELECT 1 FROM "'
                + d["head"]["relation"]
                + '" h WHERE '
                + " AND ".join(conditions)
                + ")"
            )
            query += (
                (" AND " if " WHERE " in query else " WHERE ") + absent + " LIMIT 1"
            )
            if db.execute(query, args).fetchone():
                return False
    return True


def database(schema, facts):
    db = sqlite3.connect(":memory:")
    for r in schema:
        db.execute(
            'CREATE TABLE "'
            + r["name"]
            + '"('
            + ",".join("c" + str(i) + " TEXT NOT NULL" for i in range(r["arity"]))
            + ")"
        )
        values = [f["values"] for f in facts if f["relation"] == r["name"]]
        db.executemany(
            'INSERT INTO "'
            + r["name"]
            + '" VALUES('
            + ",".join("?" for _ in range(r["arity"]))
            + ")",
            values,
        )
    return db


def main():
    cases = [c["input"] for c in controls()] + requests(100)
    terminal = 0
    queries = 0
    models = 0
    valid_models = 0
    implications = 0
    for data in cases:
        report = analyze(data)
        for d in report["directions"]:
            if d["chase"]["failed"]:
                continue
            state = d["chase"]["final_state"]
            db = database(data["schema"], state["facts"])
            assert valid(db, data["dependencies"])
            terminal += 1
            for side in ["left", "right"]:
                actual = answers(db, data[side])
                reported = set(
                    map(
                        tuple,
                        d[
                            (
                                "source_evaluation"
                                if side == d["source"]
                                else "target_evaluation"
                            )
                        ]["answers"],
                    )
                )
                assert actual == reported
                queries += 1
            frozen = tuple(state["head"])
            assert frozen in answers(db, data[d["target"]])
            assert (frozen in answers(db, data[d["source"]])) == d["contained"]
            db.close()
    # Exhaust every database over two rigid values for every original control,
    # and every dependency subset. Not a general completeness proof.
    for control in controls():
        data = control["input"]
        report = analyze(data)
        facts = [
            {"relation": r["name"], "values": list(v)}
            for r in data["schema"]
            for v in itertools.product(["c:a", "c:b"], repeat=r["arity"])
        ]
        for bits in itertools.product([False, True], repeat=len(facts)):
            db = database(data["schema"], [f for f, keep in zip(facts, bits) if keep])
            av = {s: answers(db, data[s]) for s in ["left", "right"]}
            queries += 2
            models += 1
            for subset in report["dependency_atlas"]:
                deps = [
                    data["dependencies"][i] for i in subset["retained_dependencies"]
                ]
                if not valid(db, deps):
                    continue
                valid_models += 1
                for di, (target, source) in enumerate(
                    [("left", "right"), ("right", "left")]
                ):
                    if subset["directions"][di]["contained"]:
                        assert av[target] <= av[source]
                        implications += 1
            db.close()
    out = {
        "sqlite_version": sqlite3.sqlite_version,
        "reports": len(cases),
        "valid_terminal_databases": terminal,
        "queries": queries,
        "two_value_databases": models,
        "valid_database_subset_pairs": valid_models,
        "sound_containment_implications": implications,
    }
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
