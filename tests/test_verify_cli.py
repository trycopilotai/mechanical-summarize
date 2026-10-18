"""Command-line tests for the mechanical reduction verifier.

Each test runs the shipped script as a subprocess, so the exit codes
and output the README documents are the ones a user gets.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "mechanical-summarize"
    / "scripts"
    / "verify_reduction.py"
)


def run(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
    )


def report(stdout: str) -> dict:
    lines = [line.split("=", 1) for line in stdout.splitlines() if "=" in line]
    return {key: value for key, value in lines}


class VerifyCliTests(unittest.TestCase):
    """Exercise measure and verify through the real entry point."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.write(
            "source.txt",
            "So, um, we shipped it, but it is not a full fix.\n",
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def write(self, name: str, text: str) -> str:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_measure_reports_the_ceiling_floor_and_suffix(self) -> None:
        result = run("measure", self.source, "--retain", "0.5")

        self.assertEqual(result.returncode, 0, result.stderr)
        values = report(result.stdout)
        self.assertEqual(values["source_words"], "12")
        self.assertEqual(values["target_words"], "6")
        self.assertEqual(values["suggested_suffix"], ".50per")

    def test_valid_deletion_exits_zero(self) -> None:
        candidate = self.write("copy.txt", "We shipped it, but it is not a full fix.\n")

        result = run("verify", self.source, candidate, "--retain", "0.5")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report(result.stdout)["valid"], "True")

    def test_inserted_word_exits_one(self) -> None:
        candidate = self.write("copy.txt", "We shipped it, but it is never a full fix.\n")

        result = run("verify", self.source, candidate, "--retain", "0.5")

        self.assertEqual(result.returncode, 1)
        values = report(result.stdout)
        self.assertEqual(values["valid"], "False")
        self.assertEqual(values["missing_candidate_token"], "never")

    def test_deleted_negation_is_not_detected(self) -> None:
        """Deletion shape and budget cannot see meaning; review stays manual."""
        candidate = self.write("copy.txt", "We shipped it, but it is a full fix.\n")

        result = run("verify", self.source, candidate, "--retain", "0.5")

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_punctuation_only_words_count_but_are_unchecked(self) -> None:
        """A documented limit: padding with punctuation meets the budget."""
        candidate = self.write("copy.txt", "We shipped it - - -\n")

        result = run("verify", self.source, candidate, "--retain", "0.5")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report(result.stdout)["candidate_words"], "6")

    def test_copy_below_floor_exits_one(self) -> None:
        candidate = self.write("copy.txt", "We shipped it.\n")

        result = run("verify", self.source, candidate, "--retain", "0.5")

        self.assertEqual(result.returncode, 1)
        self.assertIn("candidate_below_target_floor", report(result.stdout)["issues"])

    def test_unreadable_file_exits_two(self) -> None:
        result = run("verify", self.source, str(self.root / "absent.txt"))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_non_utf8_file_exits_two(self) -> None:
        path = self.root / "latin1.txt"
        path.write_bytes("caf\xe9 au lait\n".encode("latin-1"))

        result = run("measure", str(path))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_retention_outside_the_interval_is_refused(self) -> None:
        for value in ("0", "1.5", "NaN", "half"):
            with self.subTest(value=value):
                result = run("measure", self.source, "--retain", value)
                self.assertEqual(result.returncode, 2)

    def test_json_report_is_machine_readable(self) -> None:
        candidate = self.write("copy.txt", "We shipped it, but it is not a full fix.\n")

        result = run("verify", self.source, candidate, "--json")

        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)
        self.assertTrue(data["valid"])
        self.assertEqual(data["source_words"], 12)
        self.assertEqual(data["candidate_words"], 10)
        self.assertTrue(data["ordered_lexical_subsequence"])
        self.assertEqual(data["case_change_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
