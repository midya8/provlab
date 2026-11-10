# ProvLab0.3: the assumptions change the answer

A finite, local full-rule/key chase for constraint-relative containment of two safe positive conjunctive queries. It records every fact addition, equality substitution, ordered-head change and literal clash. Every dependency subset is tested in both directions. This is an implementation of classical database theory in a deliberately small language, not a new theorem or general SQL optimizer.

## Try it

```sh
python -m pip install .
provlab-chase examples/chase-default.json --output chase-report.json
provlab-chase chase-report.json --verify
python -m provlab.chase_cli examples/chase-default.json
python -m http.server 8000 --directory docs
# Open http://localhost:8000/chase.html
```

The certificate verifier reconstructs the complete deterministic report using Cartesian ground assignments and flat equality substitution. It does not import `chase.py`, its join evaluator or its union/parent bookkeeping. It shares strict input validation. Extra or missing fields, changed evidence and Boolean/integer type substitutions are rejected. This is independent replay, not a signed attestation or a substitute for the mathematical argument.

## The default is intentionally not just a full-rule example

```
L(x,y) :- R(k,x) & R(k,y)
Q(u,v) :- R(t,u) & R(t,v) & S(u,v)

one_value: KEY R [0]
diagonal:  R(t,u) -> S(u,u)
symmetry:  S(u,v) -> S(v,u)
```

Without assumptions, `L ⊆ Q` fails. Under the key, `n:x` and `n:y` merge. The ordered target head changes from `(n:x,n:y)` to `(n:x,n:x)`, and the diagonal rule adds `S(n:x,n:x)`. The source query then derives the chased head. Both assumptions are needed; symmetry is irrelevant. The reverse containment needs no assumptions.

A second control replaces symmetry with `R(k,x) & R(k,y) -> S(x,y)`. Its supports for `L ⊆ Q` include `{one_value,diagonal}` and `{direct}`. Both are inclusion-minimal; only `{direct}` has minimum cardinality. The interface does not call the two notions interchangeable.

## Exact syntax

- One shared schema with1..3 named relations, each unary or binary.
- Each query has1..4 body atom occurrences and at most3 variables. Both ordered heads have the same length0..2, contain distinct variables, and are safe.
- Up to3 uniquely named dependencies. A full rule has1..2 body atoms, one head atom and at most3 variables total; all head variables occur in its body. A key names a relation and a nonempty set of zero-based column positions.
- At most2 distinct literal constants across both queries and every rule. Names are short ASCII identifiers; prototype-like valid names remain data.
- Set semantics, no SQL parser, existential variables, arbitrary EGDs, denial rules, inequalities, negation, SQL NULL, bags or provenance-preservation claim. Recursive full rules are permitted because they introduce no new symbols.

## Canonical database, quotient head and containment

For `target ⊆Σ source`, start with one tableau symbol `n:v` per target variable, including output variables. Literal `c:a` values alone are rigid. All supplied literals remain in the finite domain even if currently absent from facts. Deduplicate facts under set semantics. Keep the ordered target-head tuple separately.

Repeatedly take the first active action in dependency order. Full-rule matches are ordered lexicographically by first-occurrence variable order. A match whose head fact is absent adds it. Key actions consider sorted fact-row pairs and increasing value positions. Unequal symbols are merged into their lexical minimum, which prefers a literal over a query symbol. Substitute through every fact and the ordered head. Two distinct literal values cause a terminal clash rather than a merge. Facts, aliases, domain and head are recorded after every action. Body match counts and remaining violations are reconstructed for every selected dependency.

A successful terminal chase is a finite model of the dependencies and retains a homomorphism from the target pattern with its tracked head. Its universal-model property gives the usual reverse-map containment test: the source query must derive the tracked target tuple on this chased database. ProvLab evaluates both queries, keeps the source derivations and identifies a witness derivation. If the tuple is absent from source answers, this saturated model itself is a valid finite counterexample. The initial unchased database may violate the dependencies and must not be presented as that constrained counterexample.

A literal clash means the particular target query has no satisfying answer under these dependencies. Its containment is vacuous. The report labels this `target-unsatisfiable`, omits both terminal query evaluations and does not fabricate a counterexample. This does not mean the dependency set or all databases are inconsistent. The all-empty database satisfies these positive dependencies. The interface separates vacuity from a successful nonempty match, including in support rows.

## Why termination is guaranteed here

There are at most3 target symbols and2 literals, hence at most5 symbols. With at most3 binary relations there are at most75 possible facts. A merge reduces the symbol domain, so there are at most4 merges. Between merges, each full-rule action adds a previously absent fact, hence at most75 additions per phase and at most5 phases. The conservative bound is `5*75 + 4 = 379` nonfailure actions, with at most one additional terminal clash. This is a syntax-specific proof, not an empirical timeout or an arbitrary chase-termination claim.

## Dependency supports, not global query minimization

Every one of the at most8 dependency subsets is chased independently in both directions. The report marks every inclusion-minimal support and every smallest-cardinality support. The selected subset is an assumption set, not a database-fact subset or an atom-deletion rewrite. A successful support can be vacuous, and its reason remains explicit. No globally minimum equivalent query under dependencies is claimed.

## Reproducible checks

```sh
python -m unittest discover -s tests -v
bash tools/check_wheel.sh
bash tools/check_containment_wheel.sh
bash tools/check_chase_wheel.sh
node --test --test-concurrency=1 tests/test_engine.mjs tests/test_browser.cjs tests/test_containment_engine.mjs tests/test_containment_browser.cjs tests/test_chase_engine.mjs tests/test_chase_browser.cjs
python -m pip install -r requirements-reference.txt
python tools/reference.py
python tools/containment_reference.py
python tools/chase_reference.py
```

The chase-specific checks include14 original controls and100 deterministic seeded query/rule/key requests, full native/JavaScript report equality, an independent Python replay and344 changed non-input primitive fields in the default report. Controls cover output equality, substitution to a literal, repeated-variable activation after merging, fact additions activating a key, initial and rule-induced literal clashes, empty output/bindings, a composite key, finite recursion, duplicate spelling across variable/literal namespaces, and minimal-versus-minimum supports.

`tools/chase_reference.py` uses actual SQLite SQL joins and explicit dependency-violation queries, not the generator's evaluator. In the local SQLite3.37.2 run it checked225 successful terminal models,7,618 query executions, and5,858 claimed containment implications across3,584 exhaustive two-value control databases and7,094 valid database/dependency-subset pairs. This tests the sound direction on finite controls; it is not an exhaustive test of all inputs or the theorem's completeness.

The browser test covers every control at1280,390 and320px, both containment directions, every trace state and every subset. It checks rendered facts, aliases, heads, terminal answers and obligations against native reports. Real trusted click/download events must complete, and the downloaded reports are replayed by Python. An invalid edit clears the verdict and disables certificate download rather than leaving stale results usable. Installed-wheel tests run outside the checkout with site-packages origins and both CLI entrypoints. CI runs all three installed workflows on Python3.10,3.11,3.12 and3.13.

## Source notes and boundaries

- Abiteboul, Hull and Vianu, _Foundations of Databases_ (1995), [chapter8](https://webdam.di.ens.fr/Alice/pdfs/Chapter-8.pdf), section8.4: the FD chase substitutes in the body **and the output tuple**; containment follows from the chased query. [Chapter10](https://webdam.di.ens.fr/Alice/pdfs/Chapter-10.pdf) defines full tuple-generating and equality-generating dependencies. Relevant sections were consulted, not every page of both chapters.
- Markus Krötzsch, [Database Theory lecture18](https://iccl.inf.tu-dresden.de/w/images/9/9f/DBT2019-Lecture-18-print.pdf) (July3,2019): full TGDs add no fresh domain elements; universality and the limits of existential chase termination.
- Deutsch and Nash, [Chase reference entry](http://dbucsd.github.io/paperpdfs/2008_18.pdf): constant-fixing homomorphisms, equality merges, distinct-constant failure and universality. Its shorthand about query variables as constants is not used to make head symbols rigid under keys; the explicit output substitution above matters.
- [Scalable Containment for Unions of Conjunctive Queries](https://www.southampton.ac.uk/~gk1e17/queryContainment.pdf): constraint-relative containment via chasing, used within its TGD scope, not its suggested EGD extension.
- Grahne and Onet, [Anatomy of the Chase](https://ar5iv.labs.arxiv.org/html/1303.6682): chase variants, universality and termination boundaries. No general chase result is inferred from this finite implementation.
- Barceló, Figueira, Gottlob and Pieris, [Semantic Optimization of Conjunctive Queries](https://dl.acm.org/doi/fullHtml/10.1145/3424908) (2020): containment decidability is not the same as a global semantic-optimization guarantee. This lab makes no such minimization claim.

No paid APIs, hidden model calls, private data, external telemetry or benchmark superiority claim.
