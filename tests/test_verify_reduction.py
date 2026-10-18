"""Tests for the mechanical reduction verifier."""

from __future__ import annotations

import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "mechanical-summarize"
    / "scripts"
    / "verify_reduction.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_reduction",
    SCRIPT_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load verify_reduction.py")
verify_reduction = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_reduction)


class VerifyReductionTests(unittest.TestCase):
    """Exercise word budgets and lexical subsequence checks."""

    def test_exact_half_deletion_passes(self) -> None:
        report = verify_reduction.analyze_reduction(
            "one two three four five six seven eight nine ten",
            "one three five seven nine",
            Decimal("0.5"),
            True,
            False,
        )

        self.assertTrue(report["valid"])
        self.assertEqual(report["target_words"], 5)
        self.assertEqual(report["candidate_words"], 5)
        self.assertTrue(report["ordered_lexical_subsequence"])

    def test_odd_word_count_uses_ceiling_floor(self) -> None:
        self.assertEqual(
            verify_reduction.target_word_count(683, Decimal("0.5")),
            342,
        )

    def test_candidate_below_floor_fails(self) -> None:
        report = verify_reduction.analyze_reduction(
            "one two three four five six",
            "one three",
            Decimal("0.5"),
            True,
            False,
        )

        self.assertFalse(report["valid"])
        self.assertIn(
            "candidate_below_target_floor",
            report["issues"],
        )

    def test_inserted_token_fails_subsequence(self) -> None:
        report = verify_reduction.analyze_reduction(
            "one two three four",
            "one invented three",
            Decimal("0.5"),
            True,
            False,
        )

        self.assertFalse(report["valid"])
        self.assertEqual(report["missing_candidate_token"], "invented")
        self.assertIn(
            "candidate_is_not_an_ordered_lexical_subsequence",
            report["issues"],
        )

    def test_reordered_tokens_fail_subsequence(self) -> None:
        report = verify_reduction.analyze_reduction(
            "one two three four",
            "three one",
            Decimal("0.5"),
            True,
            False,
        )

        self.assertFalse(report["valid"])
        self.assertIn(
            "candidate_is_not_an_ordered_lexical_subsequence",
            report["issues"],
        )

    def test_case_change_is_reported_and_can_be_strict(self) -> None:
        relaxed = verify_reduction.analyze_reduction(
            "before alpha after beta",
            "Alpha beta",
            Decimal("0.5"),
            True,
            False,
        )
        strict = verify_reduction.analyze_reduction(
            "before alpha after beta",
            "Alpha beta",
            Decimal("0.5"),
            True,
            True,
        )

        self.assertTrue(relaxed["valid"])
        self.assertEqual(relaxed["case_change_count"], 1)
        self.assertFalse(strict["valid"])
        self.assertIn(
            "candidate_changes_lexical_token_case",
            strict["issues"],
        )

    def test_case_change_count_is_not_limited_with_examples(self) -> None:
        source = " ".join("word" + str(index) for index in range(12))
        candidate = source.upper()

        report = verify_reduction.analyze_reduction(
            source,
            candidate,
            Decimal("1"),
            True,
            False,
        )

        self.assertTrue(report["valid"])
        self.assertEqual(report["case_change_count"], 12)
        self.assertEqual(
            len(report["case_change_examples"]),
            verify_reduction.CASE_EXAMPLE_LIMIT,
        )

    def test_skip_budget_checks_only_deletion_shape(self) -> None:
        report = verify_reduction.analyze_reduction(
            "heading body words remain footer",
            "heading footer",
            Decimal("0.5"),
            False,
            False,
        )

        self.assertTrue(report["valid"])
        self.assertIsNone(report["target_words"])

    def test_suffix_supports_integer_and_decimal_percentages(self) -> None:
        self.assertEqual(
            verify_reduction.retention_suffix(Decimal("0.5")),
            ".50per",
        )
        self.assertEqual(
            verify_reduction.retention_suffix(Decimal("0.375")),
            ".37p5per",
        )


if __name__ == "__main__":
    unittest.main()
