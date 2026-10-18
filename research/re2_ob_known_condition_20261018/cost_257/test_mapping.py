import unittest

import mapping


class MappingTests(unittest.TestCase):
    def test_rank_ties_and_feature_order(self):
        result = mapping.make_mapping({4: 2, 2: 2, 3: 1}, list(range(1, 258)))
        self.assertEqual(result["selected_cluster_ids"][:3], [1, 2, 3])
        self.assertEqual(result["cluster_id_to_feature"]["2"], 2)
        self.assertEqual(result["cluster_id_to_feature"]["4"], 4)

    def test_unknown_never_ranks(self):
        with self.assertRaises(ValueError):
            mapping.make_mapping({0: 1000, 1: 4}, [0, 1])

    def test_selection_stable_and_train_only(self):
        rows = [{"case": "a", "partition": "train", "root_cause_service": "s",
                 "inject_time": 15},
                {"case": "b", "partition": "validation", "root_cause_service": "s",
                 "inject_time": 15}]
        intervals = [{"case": x, "start": 0, "end_exclusive": 30} for x in ("a", "b")]
        first = mapping.select_windows(rows, intervals, ["s"])
        second = mapping.select_windows(list(reversed(rows)), intervals, ["s"])
        self.assertEqual(first, second)
        self.assertEqual({x["case"] for x in first["records"]}, {"a"})
        self.assertEqual(len(first["records"]), 2)

    def test_empty_selection_layers_reported(self):
        rows = [{"case": "a", "partition": "train", "root_cause_service": "s",
                 "inject_time": 0}]
        result = mapping.select_windows(rows, [{"case": "a", "start": 10,
                                                 "end_exclusive": 20}], ["s"])
        self.assertEqual(result["windows"], 1)
        self.assertEqual(result["missing"][0]["fault"], False)


if __name__ == "__main__":
    unittest.main()
