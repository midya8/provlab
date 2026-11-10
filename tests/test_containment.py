import copy, itertools, json, unittest
from provlab.containment import analyze
from provlab.containment_verify import verify
from provlab.containment_input import validate
from tools.containment_cases import controls, requests, pair, q, a


class ContainmentTests(unittest.TestCase):
    def test_controls_and_seeded_ground_reconstruction(self):
        for r in [c["input"] for c in controls()] + requests(100):
            self.assertTrue(verify(analyze(r)))

    def test_default_bag_and_provenance_are_not_set(self):
        r = analyze(controls()[0]["input"])
        self.assertTrue(r["set_equivalent"])
        d = r["directions"][0]
        self.assertEqual(
            d["target_evaluation"]["answers"][0]["uniform_bag_multiplicity"], 4
        )
        self.assertEqual(
            d["source_evaluation"]["answers"][0]["uniform_bag_multiplicity"], 2
        )
        self.assertEqual(d["target_evaluation"]["derivations"][0]["exponents"], [2])
        self.assertEqual(d["source_evaluation"]["derivations"][0]["exponents"], [1])
        self.assertEqual(r["minimization"]["left"]["minimum_masks"], [1, 2])

    def test_reverse_direction_and_finite_counterexample(self):
        r = analyze(controls()[2]["input"])
        self.assertTrue(r["directions"][0]["contained"])
        self.assertFalse(r["directions"][1]["contained"])
        d = r["directions"][1]
        t = d["counterexample_tuple"]
        self.assertIn(t, [x["tuple"] for x in d["target_evaluation"]["answers"]])
        self.assertNotIn(t, [x["tuple"] for x in d["source_evaluation"]["answers"]])

    def test_head_order_and_constant_identity(self):
        for i in [4, 6]:
            r = analyze(controls()[i]["input"])
            self.assertEqual([d["contained"] for d in r["directions"]], [False, False])
        r = analyze(controls()[5]["input"])
        self.assertEqual([d["contained"] for d in r["directions"]], [True, False])

    def test_boolean_and_ground_empty_mapping(self):
        r = analyze(controls()[10]["input"])
        self.assertTrue(r["directions"][0]["contained"])
        self.assertEqual(r["directions"][1]["candidates"][0]["mapping"], {})

    def test_minima_cover_all_safe_subsets(self):
        r = analyze(controls()[8]["input"])
        self.assertEqual(r["minimization"]["left"]["minimum_atom_count"], 2)
        self.assertEqual(r["minimization"]["left"]["minimum_masks"], [6])

    def test_every_noninput_primitive_mutation_rejected(self):
        r = analyze(controls()[0]["input"])
        paths = []

        def visit(x, p):
            if isinstance(x, dict):
                for k, v in x.items():
                    if p or k != "input":
                        visit(v, p + [k])
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    visit(v, p + [i])
            else:
                paths.append(p)

        visit(r, [])
        for p in paths:
            changed = copy.deepcopy(r)
            obj = changed
            for k in p[:-1]:
                obj = obj[k]
            val = obj[p[-1]]
            obj[p[-1]] = (
                not val
                if type(val) is bool
                else (
                    val + 1
                    if type(val) is int
                    else "forged" if type(val) is str else "not-null"
                )
            )
            with self.assertRaises(ValueError, msg=str(p)):
                verify(changed)
        print("containment mutated noninput primitive fields:", len(paths))

    def test_missing_extra_and_bool_int_are_not_equal(self):
        r = analyze(controls()[0]["input"])
        for change in [
            lambda x: x.pop("limits"),
            lambda x: x.update(extra=0),
            lambda x: x.update(set_equivalent=1),
            lambda x: x["directions"][0].update(mapping_count=True),
        ]:
            s = copy.deepcopy(r)
            change(s)
            with self.assertRaises(ValueError):
                verify(s)

    def test_schema_errors(self):
        base = controls()[0]["input"]
        for change in [
            lambda x: x.update(extra=0),
            lambda x: x["schema"][0].update(arity=True),
            lambda x: x["left"].update(head=["missing"]),
            lambda x: x["left"].update(head=["x", "x"]),
            lambda x: x["left"].update(body=[]),
            lambda x: x["left"]["body"][0].update(extra=0),
            lambda x: x["left"]["body"][0]["terms"][0].update(const="a"),
        ]:
            s = copy.deepcopy(base)
            change(s)
            with self.assertRaises(ValueError):
                validate(s)

    def test_prototype_like_names(self):
        for name in ["constructor", "__proto__", "hasOwnProperty", "toString"]:
            r = pair(
                q([name], a("constructor", name)),
                q(["y"], a("constructor", "y")),
                [{"name": "constructor", "arity": 1}],
            )
            self.assertTrue(verify(analyze(r)))

    def test_all_tiny_instances_agree_with_containment(self):
        # All16 directed relations on a two-element domain, grounded directly.
        from provlab.containment_verify import ground

        edges = list(itertools.product(["a", "b"], repeat=2))
        cases = [c["input"] for c in controls()[:5]]
        count = 0
        for request in cases:
            r = analyze(request)
            for mask in range(16):
                db = {
                    "domain": ["a", "b"],
                    "facts": [
                        {"relation": "R", "values": list(edge)}
                        for i, edge in enumerate(edges)
                        if mask >> i & 1
                    ],
                }
                sets = [
                    set(tuple(a["tuple"]) for a in ground(request[s], db)["answers"])
                    for s in ["left", "right"]
                ]
                for i, (target, source) in enumerate([(0, 1), (1, 0)]):
                    if r["directions"][i]["contained"]:
                        self.assertLessEqual(sets[target], sets[source])
                count += 1
        print("containment direct finite-instance checks:", count)
