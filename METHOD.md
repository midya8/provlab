# ProvLab method and evidence

## Question and intended distinction

How can a query use one fact twice without receiving two independent chances for it to exist? This bounded relational-provenance project makes that distinction executable. It complements propositional Horn closure and deletion work rather than renaming it: query atoms contain values and shared variables, joins enforce unification, projection collects alternative bindings, and a provenance polynomial preserves derivation multiplicity. Possible-world event probabilities form a separate interpretation.

## Semantics

A supplied relation maps each distinct value tuple to one globally unique token. Its natural coefficient is initially1. A matching conjunctive-query valuation contributes the product of its atom tokens, including repeated uses. Union-all branches and alternative valuations contribute sums. Equal monomials collect natural-number coefficients. For an answer `a`:

`P_a(X) = Σ_(successful branch, valuation producing a) Π_(atom occurrence) token(ground atom)`.

This is finite positive nonrecursive query provenance in `N[X]`, following Green, Karvounarakis and Tannen. Repeated atoms are not deduplicated. Duplicate branches are not deduplicated. A variable appearing twice in one atom imposes equality. Constants have a different tagged AST form from variables. Head variables must be safe in every branch; an empty head collects all successful valuations into the unit tuple `()`.

Mapping each token to its supplied natural-number multiplicity gives bag answer multiplicity. Zero is permitted and suppresses that bag contribution. This does not remove the token from the symbolic database or change the separate event-probability interpretation.

For Boolean existence, turn each monomial into the conjunction of its distinct tokens, and alternatives into disjunction. Every supplied base token is one Bernoulli event; using it twice is still one event. The implementation assumes these **base events** are mutually independent. Derived answers and alternative derivations need not be independent. It does not accept correlated inputs or block-independent-disjoint groups.

For each world mask `W⊆tokens`, include exactly the indicated supplied facts. Its exact probability mass is `Π_(t in W) p_t × Π_(t not in W) (1-p_t)`. For each symbolically derivable answer, sum masses of worlds in which the query produces that answer. Zero-mass worlds are kept. This is an exhaustive bounded image-of-worlds calculation, not a Monte Carlo estimate. Ordinary arithmetic substitution `P_a(p)` is displayed only as a generally invalid contrast: arithmetic sum is not Boolean union, and a reused token does not become an independent event. Coincidental equality is reported, not generalized.

All witness sets preserve every distinct monomial support. Minimal Boolean witnesses remove strict supersets. The flat used-token union is also exposed. Terminology varies across older and modern provenance sources, so the UI avoids using an unqualified "why-provenance" label for any of these different objects.

Only tuples derivable in the full symbolic database are output candidates. Failed joins and a false Boolean query give an empty output list. There is no global explicit world table when no output exists; the input still determines the single empty database when no tokens exist. This is intentional, not an assertion that the world space disappeared. Probability0 answers remain symbolically derivable and listed.

## Independent replay

`provlab.core` uses sequential partial-binding joins, a natural-polynomial counter and an explicit possible-world mass sum. Its join stages record every partial binding and ordered token use. Outputs sort by value tuple; polynomial exponent vectors sort descending; witnesses sort by bit mask; worlds enumerate masks in increasing order. Stable ordering is part of the certificate contract.

`provlab.verify` does not import `core`. For each branch and each prefix, it enumerates valuations of the prefix's variables over the active domain and looks up each ground atom in a relation-value index. It reconstructs derivation records and polynomial terms through this separate route. For every world, it directly evaluates query valuations against present token membership, rather than trusting the claimed polynomial or derivation supports. It computes answer probability by Shannon recursion, then type-exactly compares the complete reconstructed report. Shared input validation, variable first-occurrence ordering and type comparison are plumbing, not independent semantic implementations. Consistent bugs across both implementations remain possible.

The browser generator is a third implementation in JavaScript. It uses exact reduced `BigInt` fractions, not floating-point probability arithmetic. Full report equality with Python is required, not a handful of headline values.

The optional reference compiles the bounded AST to actual SQLite `SELECT ... FROM ... WHERE ... UNION ALL ...` statements. Internal table, column and alias names are generated. Constants are bound with qmark parameters. It runs ordinary tuple instances in every world, expanded bag copies for multiplicity, and token-carrying joins for provenance. SymPy constructs `Symbol` objects directly from tokens and independently expands the SQLite-returned token sequences into `Poly(..., domain=ZZ)`. It never parses an untrusted expression and does not reuse generator derivations as its provenance input. Library agreement is bounded reference evidence, not a correctness theorem.

## Reproduction and scope of checks

The default example has `p²+pq`, bag10, exact presence1/2 and invalid arithmetic contrast3/8. Its all-witness supports are `{p}` and `{p,q}`; its only minimal Boolean witness is `{p}`.

Native tests cover20 test methods,64 exhaustive binary-relation/query-pattern cases on two values,150 stable seeded positive queries, direct full-instance world re-querying, probability and multiplicity grids, six-token/64-world instances and shape/type rejection. Every one of the default certificate's93 non-input primitive fields is changed once and rejected. This mutation count excludes supplied input: a self-consistent certificate for a different valid input can be legitimate. Missing/extra fields and bool-as-int forgeries are separately rejected.

Optional SQLite/SymPy checks cover164 requests (14 controls plus150 seeded),3062 possible-database SQL queries,164 bag SQL queries and233 polynomial outputs. They also execute ordinary full-instance and token-carrying queries, which are not included in the3062 world-query count. The pinned SymPy version is1.14.0; SQLite's version varies with the Python build and is printed at runtime.

Browser parity covers all164 full reports, including233 outputs and6310 output/world records. Actual Chrome runs all14 controls at1280/390/320 widths, compares42 reports,48 selected outputs,342 world-table rows and342 selected world states, checks visible fact/derivation/world tables and every limit, edits a probability, rejects invalid input without stale results, and completes14 trusted certificate downloads. The native verifier can replay every downloaded file. Screenshot comparison is unmasked and separate from these behavior assertions. These checks do not imply industrial scale, arbitrary SQL support or a formal proof.

## Sources and what they support

1. **Green, Karvounarakis and Tannen, "Provenance Semirings", PODS2007.** Primary paper. Positive relational algebra annotations, natural polynomial provenance, valuation sums, homomorphisms and distinctions among semirings. The inspected recursive-Datalog discussion explains why finite-polynomial support must not be generalized to recursion. [Primary PDF](https://www.cs.ucdavis.edu/~green/papers/pods07.pdf)
2. **Green and Tannen, provenance/uncertainty chapter.** Primary academic chapter, inspected probability-product and world-image sections. Supports the distinction between independent base tuple events and correlated derived results. [Chapter PDF](https://www.cs.ucdavis.edu/~green/papers/models-chapter.pdf)
3. **Provenance presentation hosted by the Penn programming-languages group, PrOPr2007.** Author/academic slides, inspected in full. Corroborates sum/product annotation examples. No figure or presentation layout is copied. [Slides](https://www.cis.upenn.edu/~plclub/propr/greg-slides.pdf)
4. **ProvSQL user documentation: semirings.** Operator documentation. Modern definitions distinguish witness-set families from a flat contributor union. Older terminology is not silently merged with these names. ProvLab uses explicit labels instead. [Semirings](https://provsql.org/docs/user/semirings.html)
5. **ProvSQL user documentation: querying.** Operator documentation. Establishes the larger SQL/query-planner/circuit setting that this project does not claim to implement. ProvSQL was not installed or executed. [Querying](https://provsql.org/docs/user/querying.html)
6. **Sudeepa Roy, uncertain lineage encyclopedia article,2017.** Independent academic corroboration. Inspected article body supports Boolean lineage, tuple independence, weighted model counting, derived correlation and the general difficulty of exact inference. [Duke PDF](https://users.cs.duke.edu/~sudeepa/papers/EDBS2017-uncertain-lineage.pdf)
7. **ProvSQL user documentation: probabilities.** Operator documentation, inspected introduction and input probability/independence sections. Supports distinguishing independent tuples from block-independent-disjoint groups. No uninspected method-specific behavior is attributed to ProvSQL. [Probabilities](https://provsql.org/docs/user/probabilities.html)
8. **SymPy polynomial manipulation basics.** Official library documentation, inspected canonical coefficient/exponent/generator concepts and examples. Used with an actual pinned1.14.0 installation for the reference above. [Polynomial basics](https://docs.sympy.org/latest/modules/polys/basics.html)
9. **Python `sqlite3` documentation.** Official standard-library documentation, inspected parameter binding, `execute`, `fetchall` and in-memory connection examples. Query constants use placeholders; user strings never supply SQL identifiers. [sqlite3](https://docs.python.org/3/library/sqlite3.html)

Sources were checked November10,2026. Semantics come from these classical references; implementation design, fixtures and page are original. Source terminology and scope are preserved rather than advertised as novelty.

## Limits and nonclaims

Exhaustive `2^m` worlds with `m≤6`, finite active-domain valuations and small natural-coefficient polynomials are intentionally bounded. No SQL parser, recursion, negation, aggregation, NULL, correlated base events, causal effects, real-data probability calibration, data updates, provenance compression, query optimization, new research result or industrial performance claim. A checked supplied database is not a guarantee about retrieval quality, model behavior or an actual AI agent.
