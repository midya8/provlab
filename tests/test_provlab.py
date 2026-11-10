import ast, copy, itertools, json, random, subprocess, sys, unittest
from pathlib import Path
from fractions import Fraction
from provlab import analyze
from provlab.verify import verify
from provlab.input import load
from tools.make_controls import controls, model, R, A, V, C


class ProvLabTests(unittest.TestCase):
    def test_controls(self):
        for c in controls():
            self.assertTrue(verify(analyze(c["input"])))

    def test_default(self):
        o = analyze(controls()[0]["input"])["outputs"][0]
        self.assertEqual(
            o["terms"],
            [
                {"coefficient": 1, "exponents": [2, 0]},
                {"coefficient": 1, "exponents": [1, 1]},
            ],
        )
        self.assertEqual(o["presence_probability"], "1/2")
        self.assertEqual(o["arithmetic_probability_substitution"], "3/8")
        self.assertEqual(o["bag_multiplicity"], 10)
        self.assertEqual(o["minimal_witnesses"], [["p"]])
        self.assertEqual(o["witnesses"], [["p"], ["p", "q"]])

    def test_duplicate_branches(self):
        r = analyze(controls()[1]["input"])
        o = r["outputs"][0]
        self.assertEqual(o["terms"], [{"coefficient": 2, "exponents": [1]}])
        self.assertEqual(o["presence_probability"], "1/2")
        self.assertEqual(o["bag_multiplicity"], 4)

    def test_overlap(self):
        self.assertEqual(
            analyze(controls()[2]["input"])["outputs"][0]["presence_probability"], "3/8"
        )

    def test_empty_and_boolean(self):
        self.assertEqual(analyze(controls()[8]["input"])["outputs"], [])
        self.assertEqual(analyze(controls()[9]["input"])["outputs"][0]["tuple"], [])
        self.assertEqual(analyze(controls()[-1]["input"])["outputs"], [])

    def test_independent_import(self):
        tree = ast.parse(Path("provlab/verify.py").read_text())
        self.assertNotIn(
            "core", [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        )

    def test_every_two_value_binary_relation(self):
        cases = 0
        x = V("x")
        y = V("y")
        z = V("z")
        pairs = list(itertools.product(["a", "b"], repeat=2))
        for mask in range(16):
            for pattern in [
                [A("E", x, y), A("E", y, z)],
                [A("E", x, x)],
                [A("E", x, y), A("E", x, y)],
                [A("E", x, y), A("E", y, x)],
            ]:
                rows = [
                    ("p" + str(i), list(v), 1, "1/2")
                    for i, v in enumerate(pairs)
                    if mask >> i & 1
                ]
                r = model([R("E", 2, rows)], ["x"], [pattern])
                self.assertTrue(verify(analyze(r)))
                cases += 1
        self.assertEqual(cases, 64)

    def test_all_presence_worlds_requery(self):
        x = V("x")
        y = V("y")
        z = V("z")
        pairs = list(itertools.product(["a", "b"], repeat=2))
        base = model(
            [
                R(
                    "E",
                    2,
                    [("p" + str(i), list(v), 1, "1/2") for i, v in enumerate(pairs)],
                )
            ],
            ["x", "z"],
            [[A("E", x, y), A("E", y, z)]],
        )
        r = analyze(base)
        for output in r["outputs"]:
            for world in output["worlds"]:
                q = copy.deepcopy(base)
                q["relations"][0]["rows"] = [
                    f for f in q["relations"][0]["rows"] if f["id"] in world["present"]
                ]
                visible = [o["tuple"] for o in analyze(q)["outputs"]]
                self.assertEqual(output["tuple"] in visible, world["holds"])

    def test_multiplicity_substitution(self):
        x = V("x")
        r = copy.deepcopy(controls()[0]["input"])
        for p, q in itertools.product(range(4), repeat=2):
            r["relations"][0]["rows"][0]["multiplicity"] = p
            r["relations"][1]["rows"][0]["multiplicity"] = q
            self.assertEqual(
                analyze(r)["outputs"][0]["bag_multiplicity"], p * p + p * q
            )

    def test_probability_grid(self):
        r = copy.deepcopy(controls()[3]["input"])
        for p, q in itertools.product(
            [Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(1)], repeat=2
        ):
            r["relations"][0]["rows"][0]["probability"] = str(p)
            r["relations"][1]["rows"][0]["probability"] = str(q)
            a = analyze(r)
            self.assertTrue(verify(a))
            self.assertEqual(
                Fraction(a["outputs"][0]["presence_probability"]), p + q - p * q
            )

    def test_seeded_queries(self):
        from tools.cases import requests

        for r in requests(150):
            self.assertTrue(verify(analyze(r)))

    def test_all_default_primitive_tamper(self):
        report = analyze(controls()[0]["input"])
        count = 0

        def leaves(x, path=()):
            if type(x) is dict:
                for k, v in x.items():
                    yield from leaves(v, path + (k,))
            elif type(x) is list:
                for k, v in enumerate(x):
                    yield from leaves(v, path + (k,))
            else:
                yield path, x

        for path, v in leaves(report):
            if path[0] == "input":
                continue
            r = copy.deepcopy(report)
            d = r
            for k in path[:-1]:
                d = d[k]
            d[path[-1]] = (
                not v if type(v) is bool else v + 1 if type(v) is int else "forged"
            )
            with self.assertRaises(ValueError):
                verify(r)
            count += 1
        self.assertEqual(count, 93)

    def test_missing_extra_and_type(self):
        base = analyze(controls()[0]["input"])
        for r in [
            {**base, "extra": 1},
            {k: v for k, v in base.items() if k != "domain"},
        ]:
            with self.assertRaises(ValueError):
                verify(r)
        r = copy.deepcopy(base)
        r["outputs"][0]["derivation_count"] = True
        with self.assertRaises(ValueError):
            verify(r)

    def test_prototype_like_identifiers(self):
        for v in ["constructor", "toString", "__proto__", "hasOwnProperty"]:
            r = model(
                [R("constructor", 1, [("toString", ["__proto__"], 1, "1/2")])],
                [v],
                [[A("constructor", V(v))]],
            )
            out = analyze(r)
            self.assertTrue(verify(out))
            self.assertEqual(out["outputs"][0]["tuple"], ["__proto__"])

    def test_constant_only_and_ternary(self):
        r = model(
            [
                R(
                    "T",
                    3,
                    [
                        ("p", ["a", "a", "b"], 2, "1/3"),
                        ("q", ["a", "b", "b"], 1, "2/3"),
                    ],
                )
            ],
            [],
            [[A("T", C("a"), C("a"), C("b"))]],
        )
        out = analyze(r)
        self.assertTrue(verify(out))
        self.assertEqual(out["outputs"][0]["presence_probability"], "1/3")
        r["query"]["branches"] = [
            [A("T", V("x"), V("y"), V("z")), A("T", V("w"), V("y"), V("z"))]
        ]
        self.assertTrue(verify(analyze(r)))

    def test_six_tokens_and_sixtyfour_worlds(self):
        r = model(
            [
                R(
                    "E",
                    2,
                    [
                        ("p" + str(i), list(v), 1, "1/2")
                        for i, v in enumerate(
                            itertools.product(["a", "b"], ["a", "b", "c"])
                        )
                    ],
                )
            ],
            ["x"],
            [[A("E", V("x"), V("y"))]],
        )
        out = analyze(r)
        self.assertTrue(verify(out))
        self.assertEqual(len(out["outputs"][0]["worlds"]), 64)
        self.assertEqual(out["outputs"][0]["presence_probability"], "7/8")

    def test_input_schema(self):
        base = controls()[0]["input"]
        bad = [None, [], {}, True]
        changes = [
            lambda r: r.update(extra=1),
            lambda r: r["relations"][0].update(arity=True),
            lambda r: r["relations"][0]["rows"][0].update(probability=0.5),
            lambda r: r["relations"][0]["rows"][0].update(probability="2"),
            lambda r: r["relations"][0]["rows"][0].update(multiplicity=True),
            lambda r: r["relations"][0]["rows"][0].update(multiplicity=-1),
            lambda r: r["relations"][0]["rows"].append(
                copy.deepcopy(r["relations"][0]["rows"][0])
            ),
            lambda r: r["relations"][1]["rows"][0].update(id="p"),
            lambda r: r["relations"][0]["rows"][0].update(values=["a", "b"]),
            lambda r: r["query"].update(head=["z"]),
            lambda r: r["query"].update(branches=[[]]),
            lambda r: r["query"]["branches"][0][0].update(
                terms=[{"var": "x", "const": "a"}]
            ),
            lambda r: r["query"]["branches"][0][0].update(relation="missing"),
            lambda r: r["query"].update(head=["x", "x"]),
        ]
        for change in changes:
            r = copy.deepcopy(base)
            change(r)
            bad.append(r)
        for r in bad:
            with self.assertRaises(ValueError):
                analyze(r)

    def test_limits(self):
        base = copy.deepcopy(controls()[0]["input"])
        base["query"]["branches"] *= 3
        with self.assertRaises(ValueError):
            analyze(base)
        r = model(
            [R("E", 1, [("p" + str(i), ["v" + str(i)], 1, "1/2") for i in range(5)])],
            ["x"],
            [[A("E", V("x"))]],
        )
        with self.assertRaises(ValueError):
            analyze(r)

    def test_json_duplicates(self):
        for raw in ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}']:
            with self.assertRaises(ValueError):
                load(raw)

    def test_no_mutation_and_rational_normalization(self):
        r = copy.deepcopy(controls()[0]["input"])
        r["relations"][0]["rows"][0]["probability"] = "2/4"
        before = copy.deepcopy(r)
        a = analyze(r)
        self.assertEqual(r, before)
        self.assertEqual(a["input"]["relations"][0]["rows"][0]["probability"], "1/2")

    def test_no_generator_in_fresh_checker(self):
        code = (
            'import sys;from provlab.verify import replay;assert "provlab.core" not in sys.modules;print(replay('
            + repr(controls()[0]["input"])
            + ')["schema"])'
        )
        self.assertIn(
            "provlab-v1",
            subprocess.check_output([sys.executable, "-c", code], text=True),
        )


if __name__ == "__main__":
    unittest.main()
