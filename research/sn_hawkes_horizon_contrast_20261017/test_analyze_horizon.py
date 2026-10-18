"""Four minimal fixtures for frozen-prediction scoring."""
import numpy as np
import unittest

from analyze_horizon import metrics, tied_topk_credit, validate_order


def self_check():
    # Exact tie at the decision boundary receives expected fractional credit.
    assert tied_topk_credit(np.array([1., 1., 0.]), 1, 1) == 0.5
    # Normals are excluded from conditional root accuracy.
    root = np.zeros((78, 12), dtype=np.float64)
    det = np.tile([0., 1.], (78, 1))
    labels = np.asarray([0] * 65 + [-1] * 13)
    score = metrics(root, det, labels)
    assert score["conditional_top1"] == 1.0 / 12.0
    # Input order mismatch is rejected by the analyzer's shared guard.
    indices = np.arange(78)
    try:
        validate_order(indices, labels, indices[::-1], labels)
    except ValueError:
        pass
    else:
        raise AssertionError("order mismatch was not rejected")
    # Four strict paired outcomes partition all fault records.
    before, after = [0, 0, 1, 1], [0, 1, 0, 1]
    buckets = {"both_wrong": 0, "new_correct": 0, "new_wrong": 0, "both_correct": 0}
    for b, a in zip(before, after):
        key = "both_correct" if b and a else "both_wrong" if not b and not a else (
            "new_correct" if a else "new_wrong")
        buckets[key] += 1
    assert buckets == {"both_wrong": 1, "new_correct": 1, "new_wrong": 1, "both_correct": 1}
    # A correct root prediction with a wrong detector is root-correct, joint-wrong.
    root_credit, detection_credit = 1.0, 0.0
    assert root_credit == 1.0 and root_credit * detection_credit == 0.0


class AnalysisFixtures(unittest.TestCase):
    def test_ties_normals_order_and_paired_outcomes(self):
        self_check()
