"""Finite full rules and relational keys. No existential variables or SQL NULL."""

from .input import name
from .containment_input import validate as pair_validate, variables

LIMITS = [
    "Constraint-relative set containment for two safe positive single conjunctive queries. Schema1..3 relations, arity1..2,1..4 atom occurrences/query, at most3 variables/query, equally long ordered heads0..2 distinct safe variables.",
    "Up to3 named dependencies: a full single-head tuple-generating rule with1..2 body atoms and at most3 variables, or a relational key with a nonempty set of zero-based positions. All rule-head variables must occur in its body.",
    "At most2 distinct literal constants across both queries and all rules. All query variables, including output variables, start as mergeable n:name tableau symbols. Literal c:name values alone are rigid.",
    "Keys substitute in every fact AND the output tuple. Two unequal literal constants cannot merge: that target query is unsatisfiable under the selected dependencies, so its containment is vacuous, not a successful nonempty rewrite.",
    "A failed initial canonical database is not a constrained counterexample. Only a nonfailed saturated database satisfying all selected dependencies can witness a missing source answer.",
    "Full rules introduce no new symbols. At most5 initial symbols and75 possible unary/binary facts give a crude bound of379 add/merge steps: at most4 merges and5 phases of at most75 additions. Literal clash is a terminal failure step.",
    "Every dependency subset is tested in both directions. Minimal supports mean inclusion-minimal; minimum supports mean smallest cardinality. Supports can work by target unsatisfiability, which is labeled separately.",
    "Classical chase/universal-model theory in bounded syntax. No existential rules, arbitrary chase-termination claim, SQL parser, SQL NULL, bags, provenance-preserving optimization, arbitrary EGD, denial rule or global query-minimization guarantee.",
]


def all_constants(d):
    atoms = [a for s in ["left", "right"] for a in d[s]["body"]]
    for dep in d["dependencies"]:
        if dep["kind"] == "full":
            atoms += dep["body"] + [dep["head"]]
    return sorted({t["const"] for a in atoms for t in a["terms"] if "const" in t})


def validate(request):
    if type(request) is not dict or set(request) != {
        "schema",
        "left",
        "right",
        "dependencies",
    }:
        raise ValueError("requires exactly schema,left,right,dependencies")
    data = pair_validate({k: request[k] for k in ["schema", "left", "right"]})
    if any(r["arity"] > 2 for r in data["schema"]):
        raise ValueError("chase relation arities1..2")
    if any(len(variables(data[s]["body"])) > 3 for s in ["left", "right"]):
        raise ValueError("chase queries have at most3 variables")
    deps = request["dependencies"]
    if type(deps) is not list or len(deps) > 3:
        raise ValueError("dependencies length0..3")
    names = set()
    out = []
    relations = {r["name"]: r["arity"] for r in data["schema"]}
    for dep in deps:
        if (
            type(dep) is not dict
            or not name(dep.get("name"))
            or dep["name"] in names
            or dep.get("kind") not in ["full", "key"]
        ):
            raise ValueError("unique dependency names and full/key kinds required")
        names.add(dep["name"])
        if dep["kind"] == "key":
            if (
                set(dep) != {"name", "kind", "relation", "positions"}
                or type(dep["relation"]) is not str
                or dep["relation"] not in relations
            ):
                raise ValueError("key requires known relation and positions")
            ps = dep["positions"]
            if (
                type(ps) is not list
                or not ps
                or any(
                    type(i) is not int or not 0 <= i < relations[dep["relation"]]
                    for i in ps
                )
                or len(set(ps)) != len(ps)
            ):
                raise ValueError(
                    "key positions must be unique valid zero-based integers"
                )
            out.append(
                {
                    "name": dep["name"],
                    "kind": "key",
                    "relation": dep["relation"],
                    "positions": sorted(ps),
                }
            )
        else:
            if (
                set(dep) != {"name", "kind", "body", "head"}
                or type(dep["body"]) is not list
                or not 1 <= len(dep["body"]) <= 2
            ):
                raise ValueError(
                    "full rule requires1..2 body atoms and a single head atom"
                )
            # Reuse strict atom/schema validation without accepting existential head variables.
            check = {
                "schema": data["schema"],
                "left": {"head": [], "body": dep["body"] + [dep["head"]]},
                "right": {"head": [], "body": dep["body"] + [dep["head"]]},
            }
            normalized = pair_validate(check)["left"]["body"]
            body = normalized[:-1]
            head = normalized[-1]
            if len(variables(normalized)) > 3 or any(
                t["var"] not in variables(body) for t in head["terms"] if "var" in t
            ):
                raise ValueError(
                    "full rule head variables must be bound and total variables<=3"
                )
            out.append(
                {"name": dep["name"], "kind": "full", "body": body, "head": head}
            )
    data["dependencies"] = out
    if len(all_constants(data)) > 2:
        raise ValueError("at most2 literal constants across query pair and rules")
    return data
