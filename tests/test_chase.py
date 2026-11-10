import copy, json, unittest
from unittest.mock import patch
from provlab.chase import analyze
from provlab.chase_verify import verify
from provlab.chase_input import validate
from tools.chase_cases import controls, requests, pair, key, full
from tools.containment_cases import a, q


class ChaseTests(unittest.TestCase):
    def test_controls_and_seeded(self):
        for data in [c["input"] for c in controls()] + requests(100):
            r = analyze(data)
            self.assertTrue(verify(r))
            for d in r["directions"]:
                if not d["chase"]["failed"]:
                    self.assertTrue(
                        all(c["satisfied"] for c in d["chase"]["dependency_checks"])
                    )
                    self.assertIn(
                        d["chase"]["final_state"]["head"],
                        d["target_evaluation"]["answers"],
                    )
                    self.assertEqual(
                        d["contained"],
                        d["chase"]["final_state"]["head"]
                        in d["source_evaluation"]["answers"],
                    )

    def test_default_quotient_supports(self):
        r = analyze(controls()[0]["input"])
        d = r["directions"][0]
        self.assertFalse(d["unconstrained_contained"])
        self.assertTrue(r["set_equivalent"])
        self.assertEqual(r["minimum_support_sizes"], [2, 0])
        self.assertEqual(d["chase"]["final_state"]["head"], ["n:x", "n:x"])
        self.assertEqual(
            [s["event"]["kind"] for s in d["chase"]["trace"][1:]], ["merge", "add"]
        )
        self.assertEqual(
            [x["mask"] for x in r["dependency_atlas"] if x["minimal_support"][0]], [3]
        )

    def test_key_only_is_not_enough(self):
        r = analyze(controls()[2]["input"])
        d = r["directions"][0]
        self.assertFalse(d["contained"])
        self.assertEqual(d["counterexample_tuple"], ["n:x", "n:x"])
        self.assertTrue(all(x["satisfied"] for x in d["chase"]["dependency_checks"]))

    def test_constant_clash_is_vacuous_only(self):
        d = analyze(controls()[4]["input"])["directions"][0]
        self.assertEqual(d["reason"], "target-unsatisfiable")
        self.assertTrue(d["contained"])
        self.assertEqual(d["chase"]["failure"]["kind"], "clash")
        self.assertIsNone(d["source_evaluation"])
        self.assertIsNone(d["target_evaluation"])
        self.assertIsNone(d["counterexample_tuple"])

    def test_output_constant_substitution(self):
        d = analyze(controls()[5]["input"])["directions"][0]
        self.assertEqual(d["chase"]["final_state"]["head"], ["c:b"])
        self.assertTrue(d["contained"])

    def test_facts_activate_keys(self):
        d = analyze(controls()[8]["input"])["directions"][0]
        self.assertEqual(
            [x["event"]["kind"] for x in d["chase"]["trace"][1:]], ["add", "merge"]
        )
        self.assertEqual(d["chase"]["final_state"]["head"], ["n:x", "n:x"])

    def test_merge_activates_repeated_variable_rule(self):
        data = pair(
            q(["x", "y"], a("R", "k", "x"), a("R", "k", "y"), a("S", "x", "y")),
            q(["u", "v"], a("R", "t", "u"), a("S", "v", "v")),
            [
                key("one", "R", [0]),
                full("repeat", [a("S", "z", "z")], a("R", "z", "z")),
            ],
        )
        r = analyze(data)
        self.assertTrue(verify(r))
        events = r["directions"][0]["chase"]["trace"]
        self.assertTrue(any(x["event"] and x["event"]["kind"] == "add" for x in events))
        self.assertEqual(events[1]["event"]["kind"], "merge")

    def test_minimal_is_not_minimum(self):
        r = analyze(controls()[12]["input"])
        self.assertEqual(
            [a["mask"] for a in r["dependency_atlas"] if a["minimal_support"][0]],
            [3, 4],
        )
        self.assertEqual(
            [a["mask"] for a in r["dependency_atlas"] if a["minimum_support"][0]], [4]
        )
        self.assertEqual(r["minimum_support_sizes"][0], 1)

    def test_new_fact_then_literal_clash(self):
        d = analyze(controls()[13]["input"])["directions"][0]
        self.assertEqual(d["reason"], "target-unsatisfiable")
        self.assertEqual(
            [s["event"]["kind"] for s in d["chase"]["trace"][1:]], ["add", "clash"]
        )

    def test_checker_does_not_call_generator(self):
        r = analyze(controls()[0]["input"])
        with patch("provlab.chase.analyze", side_effect=AssertionError), patch(
            "provlab.chase.chase", side_effect=AssertionError
        ), patch("provlab.chase.joins", side_effect=AssertionError):
            self.assertTrue(verify(r))

    def test_type_and_shape_rejection(self):
        base = controls()[0]["input"]
        bad = [None, [], {}, dict(base, extra=True)]
        for field, value in [
            ("kind", []),
            ("name", {}),
            ("positions", [True]),
            ("positions", [[0]]),
            ("relation", []),
            ("positions", [0, 0]),
        ]:
            x = copy.deepcopy(base)
            x["dependencies"][0][field] = value
            bad.append(x)
        for dep in [
            full("existential", [a("R", "x", "x")], a("S", "x", "y")),
            {"name": "e", "kind": "egd"},
            key("bad", "R", []),
            full("unsafe", [a("R", "x", "x")], a("S", "y", "y")),
        ]:
            bad.append(dict(base, dependencies=[dep]))
        for x in bad:
            with self.assertRaises(ValueError):
                validate(x)

    def test_all_noninput_leaves_tamper(self):
        r = analyze(controls()[0]["input"])
        count = 0

        def paths(x, path=()):
            if isinstance(x, dict):
                for k, v in x.items():
                    if path or k != "input":
                        yield from paths(v, path + (k,))
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    yield from paths(v, path + (i,))
            else:
                yield path, x

        for path, value in paths(r):
            x = copy.deepcopy(r)
            target = x
            for k in path[:-1]:
                target = target[k]
            target[path[-1]] = (
                not value
                if type(value) is bool
                else (
                    value + 1
                    if type(value) is int
                    else "changed" if type(value) is str else 0
                )
            )
            with self.assertRaises(ValueError):
                verify(x)
            count += 1
        print("chase mutated noninput primitive fields:", count)
        self.assertGreater(count, 300)
        for x in [
            dict(r, extra=1),
            {k: v for k, v in r.items() if k != "limits"},
            dict(r, set_equivalent=1),
        ]:
            with self.assertRaises(ValueError):
                verify(x)


if __name__ == "__main__":
    unittest.main()
