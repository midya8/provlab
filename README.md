# ProvLab

**One fact is not two independent chances.** Inspect how a positive finite query derives an answer, how many bag copies it has, and how likely it is under explicitly independent base-tuple events.

The default example derives `answer(amy)` through `R(x) ∧ R(x)` or `R(x) ∧ S(x)`. Its natural-coefficient provenance is `p² + pq`. With bag multiplicities `p=2, q=3`, the answer has multiplicity `10`. With base-event probabilities `P(p)=1/2, P(q)=1/4`, its presence probability is `1/2`, **not** the ordinary arithmetic substitution `3/8`. The first route already succeeds whenever `p` exists; the second adds no new successful worlds.

This is classical provenance-semiring and tuple-independent probabilistic-database semantics in a small, inspectable implementation. It is a symbolic data-reasoning project, not a language model, new theory, a production database, or a verified AI agent. See [METHOD.md](METHOD.md) for derivations, sources, independent checks and scope.

## Run without dependencies

Python3.10 or later:

```sh
python -m provlab examples/reuse.json --output /tmp/reuse-certificate.json
python -m provlab /tmp/reuse-certificate.json --verify
python -m unittest discover -s tests -v
bash tools/check_wheel.sh
```

Or `pip install .` and use the `provlab` command. The wheel checker builds a wheel, installs into a fresh environment, leaves the checkout, verifies all14 saved full reports through both entry points, checks five `site-packages` module origins and rejects20 forged CLI certificates. Core generation and checking need only the standard library.

Serve the browser locally:

```sh
python -m http.server 8000 --directory docs
# open http://localhost:8000
node --test tests/test_engine.mjs tests/test_browser.cjs
```

Node22+ and a local `google-chrome` executable are needed for the actual Chrome checks. Set `CHROME_BIN` to another Chrome path if needed. `SCREENSHOT_DIR=/tmp/provlab-shots VERIFY_DOWNLOADS=1 npm test` saves full screenshots and independently verifies each actual completed certificate download. No browser automation package is needed.

Optional independent library/engine checks:

```sh
python -m pip install -r requirements-reference.txt
python tools/reference.py
```

The reference compiles the bounded query AST into actual SQLite joins, with generated identifiers and bound constant values. SQL produces token sequences for SymPy to expand, rather than taking generator derivations on trust. It checks164 requests,3062 possible-database queries,164 expanded-bag queries and233 polynomial outputs. SQLite's version comes from the Python build; SymPy is pinned to1.14.0. This is not a claim that the application accepts SQL or executes ProvSQL.

## Inspect the evidence

- Fourteen original controls cover token reuse, duplicate union-all branches, overlapping events, disjoint-token alternatives, projection collisions, join chains, repeated variables, tagged constants, empty answers, Boolean heads, bag zero, probability0/1, triple reuse and an empty relation.
- The browser exposes base tuples, the exact query, polynomial exponents and coefficients, all witness sets, minimal Boolean witnesses, every derivation and partial join, all possible-world masks and exact rational masses.
- Token buttons select a possible database without changing its probability. Each world is counted once, even when several derivations succeed.
- Download the complete replayable certificate. A native verifier imports no join generator: it enumerates active-domain valuations and looks up ground facts, reconstructs every certificate field and directly re-queries possible databases. Shannon recursion checks the marginal independently of the generator's world-mass sum.
- Custom JSON has strict keys, explicit variable/constant tags, bounded names, exact rational-string probabilities and rejection of duplicate JSON keys. Invalid input clears old results and disables download.

## Contract

One to three relations, arity1..3, at most6 globally unique base tokens and4 distinct data/query-constant values. No two supplied rows of one relation have the same value tuple. A query has1..4 union-all conjunctive branches,1..3 atoms per branch and at most4 variables per branch. The common safe head has0..2 distinct variables, each appearing in every branch. An empty head is a Boolean query; empty conjunctions are not allowed.

Only tuples derivable in the full symbolic input receive output records. An absent answer is not listed as a zero-probability candidate. A supplied tuple with event probability0 or bag multiplicity0 still has symbolic provenance; probability and bag interpretations remain separate. No NULLs, SQL parser, recursion, negation, aggregation, correlated base events, uncertainty calibration or scalable inference.

All arithmetic is exact: Python `Fraction`, browser `BigInt` rational arithmetic. Each output lists all `2^m` worlds for the supplied `m≤6` tokens, including zero-mass worlds and irrelevant supplied facts. Polynomial powers are retained in the natural semiring; witness sets forget reuse; minimal witnesses additionally forget Boolean-redundant supersets. These are different representations, not interchangeable explanations.

## Validation

The21 native tests include64 exhaustive two-value binary-relation/query-pattern cases,150 seeded queries, direct possible-world re-querying, a probability grid, multiplicity substitutions, all93 non-input primitive mutations of the default report, type/shape rejection, constant-only/ternary queries, four-variable bodies and six-token/64-world checks and prototype-like identifiers. The browser/native parity test compares164 full reports,233 outputs and6310 output/world records. Actual Chrome tests run all14 controls at1280,390 and320px, select every output and world, verify visible tables, reject invalid edits and complete14 trusted certificate downloads. Counts describe the committed fixtures, not a general proof.

CI runs native tests and installed-wheel checks on Python3.10/3.11/3.12/3.13, actual Chrome/browser parity checks and optional external references. Pages deployment is separate from test CI and must finish before any live-demo release claim.

## Attribution

Original project code and tiny fixtures under MIT. Classical semantics are credited in [METHOD.md](METHOD.md). CLI, installed-wheel and Chrome/CDP scaffolding adapt this portfolio's earlier BranchLab work; the strict browser JSON parser came through BranchLab from AbsorbLab. No external solver code or paper figures are copied. SymPy is an optional pinned development dependency, not vendored. Python's SQLite binding uses its bundled/system SQLite implementation. No paid service, private dataset, benchmark claim, invented contributor or model-training claim.

## 0.2: same answers on every database?

[Live containment lab](https://midya8.github.io/provlab/containment.html) · [Exact contract and reproduction](CONTAINMENT.md)

Compare safe single conjunctive queries in both directions with reverse homomorphisms, full canonical counterexamples, and every atom-subset minimum. Set equivalence is explicitly contrasted with bag counts and natural provenance. The0.1 data-provenance engine remains separate. See the method for exact bounds, classical sources and finite reference checks.

## ProvLab0.3: the assumptions change the answer

A separate finite [full-rule/key chase workbench](https://midya8.github.io/provlab/chase.html) adds constraint-relative containment, a complete fact/merge trace, ordered-head substitution, valid saturated counterexamples and explicitly labeled literal-clash vacuity. It tests every dependency subset and distinguishes inclusion-minimal supports from minimum-cardinality supports. The default needs both a key and a diagonal full rule; neither alone proves the rewrite. A separate control has a one-rule minimum support and a two-rule inclusion-minimal support.

[Method and checks](CHASE.md) · [Default input](examples/chase-default.json) · [Independent replay](provlab/chase_verify.py). No existential rules, arbitrary EGDs, SQL NULL, bag-preserving optimization or global constrained query-minimization claim. Earlier provenance and unconstrained-containment modules remain available.
