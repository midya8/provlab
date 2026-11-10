"""Strict positive single-CQ comparison schema, separate from data provenance."""

from .input import name

LIMITS = [
    "Two safe positive single conjunctive queries on one supplied relational schema. Set semantics only: no union, inequalities, negation, recursion, NULL or database dependencies.",
    "One to three relations of arity1..3. Each body has1..4 atom occurrences and at most4 variables; both ordered heads have the same arity0..2 and distinct variables.",
    "At most2 distinct literal constants across the query pair. Constants are fixed; variables may merge and may map to constants. Head positions must be preserved.",
    "Containment left ⊆ right requires a homomorphism right → left. Matching one supplied database is not the containment test.",
    "Canonical values v:name are fresh frozen variable symbols; c:name are distinct literal symbols. All supplied constants remain available in the finite domain even when absent from the canonical facts.",
    "Every safe nonempty atom subset is checked. Empty bodies and subsets that lose a head variable are explicitly outside the minimization candidate contract.",
    "Set-equivalent minimization is not permission to preserve bag multiplicities or natural-polynomial provenance. Canonical bag probes use uniform base multiplicity2 and are examples, not a bag-equivalence decision procedure.",
    "Classical Chandra-Merlin homomorphism and core theory in bounded syntax, not new theory, arbitrary SQL optimization, industrial scale or a guarantee about an AI system.",
]


def variables(body):
    result = []
    for atom in body:
        for term in atom["terms"]:
            if "var" in term and term["var"] not in result:
                result.append(term["var"])
    return result


def constants(queries):
    return sorted(
        {
            t["const"]
            for q in queries
            for a in q["body"]
            for t in a["terms"]
            if "const" in t
        }
    )


def validate(request):
    if type(request) is not dict or set(request) != {"schema", "left", "right"}:
        raise ValueError("comparison requires exactly schema,left,right")
    schema = request["schema"]
    if type(schema) is not list or not 1 <= len(schema) <= 3:
        raise ValueError("schema length1..3")
    relations = {}
    normalized = []
    for relation in schema:
        if (
            type(relation) is not dict
            or set(relation) != {"name", "arity"}
            or not name(relation["name"])
            or relation["name"] in relations
            or type(relation["arity"]) is not int
            or not 1 <= relation["arity"] <= 3
        ):
            raise ValueError("unique relation name and arity1..3 required")
        relations[relation["name"]] = relation["arity"]
        normalized.append(dict(relation))
    queries = []
    for side in ["left", "right"]:
        q = request[side]
        if type(q) is not dict or set(q) != {"head", "body"}:
            raise ValueError("query requires head and body")
        head = q["head"]
        body = q["body"]
        if (
            type(head) is not list
            or len(head) > 2
            or any(not name(v) for v in head)
            or len(head) != len(set(head))
        ):
            raise ValueError("head needs0..2 distinct variables")
        if type(body) is not list or not 1 <= len(body) <= 4:
            raise ValueError("body length1..4")
        atoms = []
        for atom in body:
            if (
                type(atom) is not dict
                or set(atom) != {"relation", "terms"}
                or type(atom["relation"]) is not str
                or atom["relation"] not in relations
            ):
                raise ValueError("atom requires known relation and terms")
            terms = atom["terms"]
            if type(terms) is not list or len(terms) != relations[atom["relation"]]:
                raise ValueError("atom arity mismatch")
            if any(
                type(t) is not dict
                or len(t) != 1
                or next(iter(t)) not in {"var", "const"}
                or not name(next(iter(t.values())))
                for t in terms
            ):
                raise ValueError(
                    "term needs exactly var or const with short ASCII name"
                )
            atoms.append(
                {"relation": atom["relation"], "terms": [dict(t) for t in terms]}
            )
        vs = variables(atoms)
        if len(vs) > 4 or any(h not in vs for h in head):
            raise ValueError("unsafe head or more than4 variables")
        queries.append({"head": head[:], "body": atoms})
    if len(queries[0]["head"]) != len(queries[1]["head"]):
        raise ValueError("head arities must agree")
    if len(constants(queries)) > 2:
        raise ValueError("at most2 literal constants")
    return {"schema": normalized, "left": queries[0], "right": queries[1]}
