import unittest

from research.tt_trace_origin_20261014 import labels


class LabelTests(unittest.TestCase):
    def test_fractional_start_and_end(self):
        record = {"faults": [{"name": "dockercomposemanifests_ts-food-service_1",
                              "fault": "network_delay", "start": .5, "duration": 10}]}
        faults = labels.rounded_faults(record, ["ts-food-service"])
        self.assertEqual(faults[0]["root"], 0)
        self.assertEqual(faults[0]["start"], 57600)
        self.assertEqual(len(labels.hits(57600, faults)), 1)
        self.assertEqual(len(labels.hits(57610, faults, fractional=True)), 1)
        self.assertEqual(len(labels.hits(57611, faults)), 0)

    def test_exact_end_boundary_difference_is_visible(self):
        record = {"faults": [{"name": "dockercomposemanifests_ts-food-service_1",
                              "fault": "network_loss", "start": 0., "duration": 10}]}
        faults = labels.rounded_faults(record, ["ts-food-service"])
        self.assertEqual(len(labels.hits(57610, faults)), 1)
        self.assertEqual(len(labels.hits(57610, faults, fractional=True)), 0)

    def test_unknown_service_rejected(self):
        with self.assertRaises(ValueError):
            labels.rounded_faults({"faults": [{"name": "dockercomposemanifests_unknown_1"}]},
                                  ["ts-food-service"])


if __name__ == "__main__":
    unittest.main()
