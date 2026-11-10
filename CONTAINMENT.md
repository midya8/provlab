# ProvLab0.2: a rewrite has to work everywhere

[Interactive containment lab](https://midya8.github.io/provlab/containment.html). Original MIT implementation of classical set-CQ containment, frozen canonical counterexamples and minimum atom-subset queries. The0.1 data-provenance engine and UI remain separate and unchanged except for a navigation link.

## The decision

For safe positive single conjunctive queries `L` and `R` with equally long ordered heads:

`L ⊆ R` on every finite database iff a head-preserving homomorphism `R → L` exists.

The arrow is reversed. The map fixes literal constants, may merge existential variables and may map variables to constants. It preserves every source atom, its relation name, arity and repeated positions, plus each ordered head position. Repeated atom occurrences are permitted; under set semantics they do not create extra distinct facts.

Each direction emits every candidate variable map, including failing candidates, exact image atoms, all matching target atom occurrences, head images, validity and the indices of every valid map. There is no inference from testing a few databases.

## A concrete counterexample

The target query's canonical database has one distinct frozen value `v:name` for each target variable and one fixed value `c:name` for each literal. Prefixes make these namespaces disjoint even when a variable and constant have the same text. Each distinct target atom becomes one fact. Duplicate target atom occurrences refer to that same fact. All constants mentioned anywhere in the pair are in the finite domain, even if they have no facts.

The target query returns its frozen ordered head tuple on this database. The source query returns it iff a valid reverse map exists. When containment fails, the report includes this tuple and both full canonical evaluations, rather than an unsupported claim that no map was found. The empty Boolean tuple `()` is a real output when a Boolean query holds; it is not a fabricated answer when the query fails. A ground constant-only query has one empty variable mapping.

## Minimum subsets, with output anchors

For each input query with `m` atom occurrences the atlas covers all `2^m` occurrence masks, including explicit excluded states. The head is unchanged. Empty bodies and subsets that lose a head variable are excluded. Every other subset is a CQ; the full body always implies the subset. We test the converse through a map `full → subset`. Every set-equivalent subset is marked; all subsets of globally smallest atom count are exposed. The classical minimum-CQ theorem guarantees an equivalent minimum can be obtained as an atom subset, unique up to head-preserving variable renaming. We do not claim literal uniqueness of an occurrence mask, and this is not an unanchored graph-core computation.

The interactive nontrivial example `R(x,y) ∧ R(x,z) ∧ R(z,w)` minimizes to atoms1 and2, mask6. It must retain the connected length-two path. An initial local test expected masks3 and5; the independent grounded checker and actual SQLite rejected that assumption. The expectation and example prose were corrected before publication. The repeated-identical-atom control has two distinct one-occurrence minimum masks,1 and2.

## Why this does not optimize arbitrary SQL

The default comparison is `R(x,y) ∧ R(x,y)` against `R(u,v)`. They are set-equivalent. On the left canonical fact, uniform base multiplicity2 gives bag counts4 versus2, and natural provenance `f0^2` versus `f0`. Set containment/minimization is not permission to preserve SQL bags or provenance. The finite bag/provenance evaluations on each canonical database are examples, not a decision procedure for bag equivalence or a proof that an arbitrary non-default equivalent pair differs under bags.

The lab handles single positive CQs,1..3 relations of arity1..3,1..4 body atom occurrences/query, at most4 variables/query,0..2 distinct safe head variables and at most2 distinct literal constants across the pair. It does not handle unions, inequalities, equalities as separate predicates, dependencies/keys, chase, NULL, recursion, negation, aggregation, schema inference, correlation or SQL parsing. No new theorem, scalable optimizer, benchmark win, calibrated data or verified-AI-agent claim.

## Reproduction

```sh
python -m unittest discover -s tests -v
node --test --test-concurrency=1 tests/test_engine.mjs tests/test_browser.cjs tests/test_containment_engine.mjs tests/test_containment_browser.cjs
python -m pip install -r requirements-reference.txt
python tools/reference.py
python tools/containment_reference.py
bash tools/check_wheel.sh
bash tools/check_containment_wheel.sh
python -m provlab.containment_cli examples/containment-default.json --output /tmp/report.json
python -m provlab.containment_cli /tmp/report.json --verify
# Installed equivalents:
provlab-containment examples/containment-default.json --output /tmp/report.json
provlab-containment /tmp/report.json --verify
```

Generation uses sequential target-fact joins for evaluation. `containment_verify.py` does not import `containment.py`: it enumerates active-domain valuations, directly grounds atoms against a fact lookup, reconstructs derivations/answers, and independently checks the canonical head membership and all minimization subsets. It replays every field with exact type/shape comparisons; it does not merely test a reported Boolean. The shared input module and classical homomorphism theorem are not independent. Changing a report's `input` and consistently recomputing it is a new request, not evidence of tampering with the old one. There is no signature or external identity guarantee.

Actual SQLite receives generated table/column aliases and parameter-bound constants. `SELECT DISTINCT` checks set answers; real duplicated base rows and `SELECT ALL` check bag counts. A third token-carrying join projects the token for each atom occurrence; SymPy constructs symbols from those rows and compares the expanded polynomial. No SQL parser or string-to-expression evaluation is used. These checks validate finite examples, not the classical theorem.

Browser/native parity covers all12 controls plus100 seeded requests, including17,403 candidate maps and1,662 subset rows. Actual Chrome checks36 control/width combinations at1280,390,320px, both directions,1,260 candidate selections,240 subset selections and12 genuinely completed trusted downloads that the installed-style native verifier replays. All235 non-input primitive fields in the default report are individually mutated and rejected, with missing/extra/type changes checked too. Eighty direct two-value relation-instance checks exercise sound directions. These counts describe the test suite, not an external benchmark or exhaustive coverage of the entire bounded input space.

## Attribution and source grounding

All code, controls and diagrams are original MIT material. The strict JSON parser, CLI conventions, installed-reproduction and Chrome download harness extend this repository's0.1 work; the UI deliberately retains its identity. SymPy is an optional pinned reference dependency, not vendored. SQLite is Python's actual linked engine.

- Chandra and Merlin, *Optimal implementation of conjunctive queries in relational data bases*, STOC1977: [primary paper](https://www.cs.ubc.ca/~laks/cpsc504/chandra-merlin-1977.pdf). Query minimization and uniqueness up to isomorphism. Intro and relevant minimization passages inspected, not a claim to have read every proof in the paper.
- Paris Koutris, Wisconsin CS784, [Lecture2: Query Containment](https://pages.cs.wisc.edu/~paris/lecture-notes/lecture2.pdf). Reverse homomorphism theorem, canonical database, minimum atom subsets. Whole fetched lecture inspected.
- Dan Suciu, DB Theory Fall2023, [Unit2 hosted by Berkeley](https://berkeley-cs294-248.github.io/lectures/unit2.pdf). Fixed constants/heads, cores and the SQL bag warning. Relevant sections inspected.
- Markus Krötzsch, FDQL2015, [Lecture8](https://iccl.inf.tu-dresden.de/w/images/7/7d/FDQLSS15-lecture-08.pdf). Fixed constants and head positions; canonical converse and minimization. Relevant sections inspected.
- Northeastern CS7240, [L9: Query containment and homomorphisms](https://northeastern-datalab.github.io/cs7240/sp20/download/cs7240-L9-Equivalence.pdf). Reverse-map composition proof and examples. Relevant sections inspected.
- SQLite, [SELECT documentation](https://sqlite.org/lang%5Fselect.html). Actual DISTINCT versus default ALL behavior. Duplicate-removal section inspected.
