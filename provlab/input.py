"""Strict bounded finite positive query contract."""

import re
from fractions import Fraction
from json import loads

LIMITS = [
    "At most six distinct base-tuple tokens across one to three supplied relations, arity1..3; at most four distinct values including query constants.",
    "One to four union-all conjunctive branches, one to three atoms per branch, at most four variables per branch; a common safe head has zero to two distinct variables.",
    "Positive finite queries only. No SQL parser, recursion, negation, aggregation, NULL, updates, inferred schema or correlated base events.",
    "How-provenance uses natural coefficients and preserves repeated token powers. Duplicate branches and repeated atoms are not silently idempotent.",
    "Bag multiplicities and existence probabilities are separate interpretations of the same supplied tokens. A multiplicity is not a probability.",
    "Exact answer-presence probability sums Boolean-query worlds under explicitly independent base-tuple events. Reusing a token is the same event, not a fresh draw.",
    "Ordinary arithmetic substitution of input probabilities into a how-provenance polynomial is shown only as a generally invalid marginal-probability contrast.",
    "Classical provenance semirings and exhaustive bounded inference, not new theory, a scalable database engine, calibrated data, causal effects or a verified AI agent.",
]


def name(x):
    return (
        type(x) is str and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,15}", x) is not None
    )


def probability(x):
    if (
        type(x) is not str
        or re.fullmatch(r"(?:0|[1-9][0-9]{0,2})(?:/[1-9][0-9]{0,2})?", x) is None
    ):
        raise ValueError("probability needs bounded rational string")
    q = Fraction(x)
    if not 0 <= q <= 1:
        raise ValueError("probability outside0..1")
    return str(q)


def variables(atoms):
    out = []
    for a in atoms:
        for t in a["terms"]:
            if "var" in t and t["var"] not in out:
                out.append(t["var"])
    return out


def validate(d):
    if type(d) is not dict or set(d) != {"relations", "query"}:
        raise ValueError("request needs exactly relations and query")
    rs = d["relations"]
    q = d["query"]
    if type(rs) is not list or not 1 <= len(rs) <= 3:
        raise ValueError("relations length1..3")
    relation_names = []
    ids = []
    domain = set()
    out = []
    for r in rs:
        if (
            type(r) is not dict
            or set(r) != {"name", "arity", "rows"}
            or not name(r["name"])
            or r["name"] in relation_names
            or type(r["arity"]) is not int
            or not 1 <= r["arity"] <= 3
        ):
            raise ValueError("invalid relation name or arity")
        relation_names.append(r["name"])
        rows = []
        seen = []
        if type(r["rows"]) is not list:
            raise ValueError("rows must be list")
        for row in r["rows"]:
            if (
                type(row) is not dict
                or set(row) != {"id", "values", "multiplicity", "probability"}
                or not name(row["id"])
                or row["id"] in ids
            ):
                raise ValueError("unique base token id required")
            ids.append(row["id"])
            if len(ids) > 6:
                raise ValueError("at most six base tokens")
            vs = row["values"]
            m = row["multiplicity"]
            if (
                type(vs) is not list
                or len(vs) != r["arity"]
                or any(not name(v) for v in vs)
                or vs in seen
            ):
                raise ValueError("unique relation tuples matching arity required")
            if type(m) is not int or not 0 <= m <= 9:
                raise ValueError("multiplicity integer0..9 required")
            seen.append(vs)
            domain.update(vs)
            rows.append(
                {
                    "id": row["id"],
                    "values": vs[:],
                    "multiplicity": m,
                    "probability": probability(row["probability"]),
                }
            )
        out.append({"name": r["name"], "arity": r["arity"], "rows": rows})
    if type(q) is not dict or set(q) != {"head", "branches"}:
        raise ValueError("query needs exactly head and branches")
    head = q["head"]
    branches = q["branches"]
    if (
        type(head) is not list
        or len(head) > 2
        or any(not name(x) for x in head)
        or len(head) != len(set(head))
    ):
        raise ValueError("head needs0..2 unique variable names")
    if type(branches) is not list or not 1 <= len(branches) <= 4:
        raise ValueError("branches length1..4")
    bs = []
    for body in branches:
        if type(body) is not list or not 1 <= len(body) <= 3:
            raise ValueError("branch body length1..3")
        atoms = []
        for a in body:
            if (
                type(a) is not dict
                or set(a) != {"relation", "terms"}
                or type(a["relation"]) is not str
                or a["relation"] not in relation_names
            ):
                raise ValueError("atom needs known relation and terms")
            arity = out[relation_names.index(a["relation"])]["arity"]
            if type(a["terms"]) is not list or len(a["terms"]) != arity:
                raise ValueError("atom arity mismatch")
            terms = []
            for t in a["terms"]:
                if (
                    type(t) is not dict
                    or len(t) != 1
                    or next(iter(t)) not in {"var", "const"}
                    or not name(next(iter(t.values())))
                ):
                    raise ValueError(
                        "term must be exactly var or const with short ASCII name"
                    )
                if "const" in t:
                    domain.add(t["const"])
                terms.append(dict(t))
            atoms.append({"relation": a["relation"], "terms": terms})
        vs = variables(atoms)
        if len(vs) > 4 or any(h not in vs for h in head):
            raise ValueError(
                "at most4variables, every head variable must occur in each branch"
            )
        bs.append(atoms)
    if len(domain) > 4:
        raise ValueError("at most four distinct data/query-constant values")
    return {"relations": out, "query": {"head": head[:], "branches": bs}}


def load(raw):
    def obj(ps):
        d = {}
        for k, v in ps:
            if k in d:
                raise ValueError("duplicate JSON key")
            d[k] = v
        return d

    def bad(x):
        raise ValueError("nonfinite JSON constant")

    return loads(raw, object_pairs_hook=obj, parse_constant=bad)


def equal(a, b, path="$"):
    if type(a) is not type(b):
        raise ValueError("type mismatch at " + path)
    if type(a) is dict:
        if set(a) != set(b):
            raise ValueError("key mismatch at " + path)
        for k in a:
            equal(a[k], b[k], path + "." + k)
    elif type(a) is list:
        if len(a) != len(b):
            raise ValueError("length mismatch at " + path)
        for i, (v, w) in enumerate(zip(a, b)):
            equal(v, w, path + "[" + str(i) + "]")
    elif a != b:
        raise ValueError("value mismatch at " + path)
