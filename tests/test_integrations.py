#!/usr/bin/env python3
"""Packaging contract: README, manifests, skill, evidence, and assets agree.

Standard library only. Needs a git clone for the history tests.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import struct
import subprocess
import types
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "mechanical-summarize"
SKILL_DIR = ROOT / "skills" / NAME
README = (ROOT / "README.md").read_text(encoding="utf-8")
CLAIM = "Shorten prose to a word budget by deleting, never rewriting."


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


BUILD = module("build_assets", "assets/build.py")
VERIFIER_PATH = "skills/mechanical-summarize/scripts/verify_reduction.py"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def release_ref():
    """The evidence belongs to one release; use its tag when the clone has it.

    Later commits may change the skill without re-recording the agent
    runs, so the evidence is checked against the release it was recorded
    for. Before the tag exists, the working tree stands in for it.
    """
    release = load("evidence/manifest.json")["release"]
    if git("rev-parse", "-q", "--verify", "refs/tags/" + release).returncode == 0:
        return "refs/tags/" + release
    return None


def release_bytes(path):
    ref = release_ref()
    if ref is None:
        return (ROOT / path).read_bytes()
    return subprocess.run(["git", "-C", str(ROOT), "show", ref + ":" + path], capture_output=True, check=True).stdout


def release_text(path):
    return release_bytes(path).decode("utf-8")


def release_verifier():
    """The verifier as released, so later verifier changes leave the evidence alone."""
    loaded = types.ModuleType("released_verify_reduction")
    exec(compile(release_bytes(VERIFIER_PATH), VERIFIER_PATH, "exec"), loaded.__dict__)
    return loaded


def sections(text):
    """Return (heading, body) for every second-level section."""
    found, heading, body = [], None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading is not None:
                found.append((heading, "\n".join(body).strip()))
            heading, body = line[3:], []
        elif heading is not None:
            body.append(line)
    if heading is not None:
        found.append((heading, "\n".join(body).strip()))
    return found


def frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md has no frontmatter"
    return [line.split(":", 1)[0] for line in match.group(1).splitlines() if re.match(r"^[a-z]", line)]


def envelope(text):
    """Every line outside a unit body: comments, titles, headings."""
    return [line for line in text.splitlines() if line.startswith(("<!--", "#"))]


def results(manifest):
    """Per-unit and aggregate counts, recomputed with the released verifier and input."""
    retain = Decimal(manifest["retain"])
    verify = release_verifier()
    source_units = sections(release_text(manifest["input"]["path"]))
    rows = []
    for run in manifest["invocations"]:
        copy_units = sections((ROOT / run["output"]["path"]).read_text(encoding="utf-8"))
        totals = [0, 0, 0]
        for (heading, source), (copy_heading, copy) in zip(source_units, copy_units):
            assert heading == copy_heading, (run["product"], heading, copy_heading)
            report = verify.analyze_reduction(source, copy, retain, True, False)
            rows.append((run["product"], heading, report))
            totals[0] += report["source_words"]
            totals[1] += report["target_words"]
            totals[2] += report["candidate_words"]
        rows.append((run["product"], "Both units", {
            "source_words": totals[0],
            "target_words": totals[1],
            "candidate_words": totals[2],
            "retained_percent": totals[2] / totals[0] * 100,
            "valid": None,
        }))
    return rows


class PackagingTest(unittest.TestCase):
    def test_manifests_agree(self):
        claude = load(".claude-plugin/plugin.json")
        codex = load(".codex-plugin/plugin.json")
        for key in ("name", "version", "description", "license", "skills", "homepage", "repository", "author"):
            self.assertEqual(claude[key], codex[key], key)
        self.assertEqual(claude["name"], NAME)
        self.assertEqual(claude["skills"], "./skills/")
        self.assertIn(f"${NAME}", " ".join(codex["interface"]["defaultPrompt"]))

    def test_skill_symlink_points_at_the_real_directory(self):
        link = ROOT / "skill"
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(link.readlink()).as_posix(), f"skills/{NAME}")
        self.assertTrue(SKILL_DIR.is_dir() and not SKILL_DIR.is_symlink())

    def test_skill_frontmatter_and_length(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(frontmatter(text), ["name", "description"])
        self.assertIn(f"name: {NAME}\n", text)
        self.assertLess(len(text.splitlines()), 500)

    def test_openai_yaml_names_the_skill(self):
        text = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("display_name:", text)
        self.assertIn(f"${NAME}", text)

    def test_codex_interface_matches_openai_yaml(self):
        """Display fields agree; the default prompts differ on purpose.

        agents/openai.yaml belongs to the skill and names the standalone
        form; this repository's Codex plugin manifest names the form that
        loads the skill from a plugin install (evidence/codex-plugin-forms/).
        Codex ignores a plugin manifest's default prompt longer than 128
        characters; both are kept within that. The
        trycopilotai/skills validator requires the two prompts to be
        equal, so that listing carries the openai.yaml form; the README
        says so.
        """
        text = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        interface = load(".codex-plugin/plugin.json")["interface"]
        display = re.search(r'display_name: "([^"]+)"', text).group(1)
        short = re.search(r'short_description:\s*"([^"]+)"', text).group(1)
        prompt = " ".join(re.search(r'default_prompt:\s*"([^"]+)"', text).group(1).split())
        self.assertEqual(interface["displayName"], display)
        self.assertEqual(interface["shortDescription"], short)
        self.assertIn(f"${NAME} ", prompt)
        self.assertLessEqual(len(prompt), 128)
        self.assertEqual(len(interface["defaultPrompt"]), 1)
        plugin_prompt = interface["defaultPrompt"][0]
        self.assertIn(f"${NAME}:{NAME} ", plugin_prompt)
        self.assertLessEqual(len(plugin_prompt), 128, "Codex ignores a longer default prompt")

    def test_codex_plugin_probes_match_the_documented_forms(self):
        """Only the namespaced form loaded the skill, and only once installed."""
        forms = load("evidence/manifest.json")["codex_plugin_forms"]
        # The probed plugin held exactly the release's Codex-facing files.
        ref = release_ref()
        listing = ["ls-tree", "-r", "--name-only", ref] if ref else ["ls-files"]
        released = git(*listing, "--", ".codex-plugin/plugin.json", "skills").stdout.split()
        self.assertEqual(sorted(record["path"] for record in forms["plugin_files"]), sorted(released))
        for record in forms["plugin_files"]:
            self.assertEqual(hashlib.sha256(release_bytes(record["path"])).hexdigest(), record["sha256"], record["path"])
        probes = forms["probes"]
        skill = release_text("skills/" + NAME + "/SKILL.md")
        first_invariant = skill.split("## Invariants\n\n", 1)[1].splitlines()[0]
        loaded = {}
        for probe in probes:
            self.assertEqual(sha256(probe["prompt"]["path"]), probe["prompt"]["sha256"])
            self.assertEqual(sha256(probe["answer"]["path"]), probe["answer"]["sha256"])
            prompt = (ROOT / probe["prompt"]["path"]).read_text(encoding="utf-8")
            answer = (ROOT / probe["answer"]["path"]).read_text(encoding="utf-8").strip()
            self.assertTrue(prompt.startswith(probe["form"] + " "))
            self.assertEqual(probe["loaded"], answer == first_invariant, probe["form"])
            if not probe["loaded"]:
                self.assertEqual(answer, "NOT LOADED")
            loaded[(probe["plugin_installed"], probe["form"])] = probe["loaded"]
        self.assertEqual(loaded, {
            (False, f"${NAME}:{NAME}"): False,
            (True, f"${NAME}"): False,
            (True, f"${NAME}:{NAME}"): True,
            (True, f"@{NAME}"): False,
        })

    def test_every_path_named_in_skill_exists(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        named = set(re.findall(r"\]\((references/[\w./-]+)\)", text))
        named |= set(re.findall(r"<skill-dir>/([\w./-]+)", text))
        self.assertIn("scripts/verify_reduction.py", named)
        for path in sorted(named):
            self.assertTrue((SKILL_DIR / path).is_file(), path)

    def test_skill_commands_resolve_from_an_install(self):
        """An installed copy has no repository root, so no command may assume one."""
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("skill/scripts/", text)
        self.assertEqual(len(re.findall(r"^python3 <skill-dir>/scripts/verify_reduction\.py ", text, re.M)), 3)


class ReadmeTest(unittest.TestCase):
    def test_claim_line_is_directly_under_the_title(self):
        self.assertEqual(README.splitlines()[:3], ["# " + NAME, "", CLAIM])
        self.assertLessEqual(len(CLAIM), 60)
        self.assertEqual(BUILD.CLAIM, CLAIM)

    def test_install_pins_match_the_manifest_version(self):
        version = load(".claude-plugin/plugin.json")["version"]
        pins = re.findall(r"^release=(v\S+)$", README, re.M)
        self.assertEqual(len(pins), 2)
        self.assertEqual(set(pins), {"v" + version})

    def test_install_blocks_copy_the_real_directory(self):
        """Git for Windows checks symlinks out as files, so never copy through skill/."""
        copies = re.findall(r'^cp -R "\$install_tmp/clone/([^"]+)" ', README, re.M)
        self.assertEqual(copies, [f"skills/{NAME}/.", f"skills/{NAME}/."])
        targets = re.findall(r'^install_target="([^"]+)"$', README, re.M)
        self.assertEqual(targets, [f"$HOME/.claude/skills/{NAME}", f"$HOME/.agents/skills/{NAME}"])

    def test_every_invocation_form_is_documented(self):
        for form in (f"/{NAME}", f"/{NAME}:{NAME}", f"${NAME}", f"${NAME}:{NAME}"):
            self.assertIn(f"`{form}`", README, form)

    def test_relative_links_resolve(self):
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", README):
            if re.match(r"^[a-z]+:", target):
                continue
            self.assertTrue((ROOT / target).exists(), target)
        for target in re.findall(r'(?:src|srcset)="([^"]+)"', README):
            self.assertTrue((ROOT / target).exists(), target)

    def test_not_measured_is_stated_up_front(self):
        head = README.split("## What it does")[0]
        self.assertIn("**Not measured, stated up front.**", head)

    def test_results_table_matches_the_verifier(self):
        for product, unit, report in results(load("evidence/manifest.json")):
            row = "| %s | %s | %d | %d | %d | %.1f%% |" % (
                product,
                unit,
                report["source_words"],
                report["target_words"],
                report["candidate_words"],
                report["retained_percent"],
            )
            self.assertIn(row, README)

    def test_docs(self):
        self.assertTrue((ROOT / "LICENSE").read_text().startswith("MIT License"))
        self.assertIn("trycopilotai/mechanical-summarize/security", (ROOT / "SECURITY.md").read_text())
        self.assertIn("make check", (ROOT / "CONTRIBUTING.md").read_text())


class HistoryTest(unittest.TestCase):
    def test_release_history_has_no_co_author_trailer(self):
        """Only the released history is checked; later contributions may carry trailers."""
        log = git("log", "--format=%B", release_ref() or "HEAD")
        self.assertEqual(log.returncode, 0, log.stderr)
        self.assertNotRegex(log.stdout, re.compile(r"^co-authored-by:", re.I | re.M))

    def test_release_tag_matches_the_manifest_version(self):
        tag = git("describe", "--tags", "--exact-match", "HEAD")
        if tag.returncode != 0:
            self.skipTest("HEAD carries no tag")
        self.assertEqual(tag.stdout.strip(), "v" + load(".claude-plugin/plugin.json")["version"])


class EvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load("evidence/manifest.json")

    def test_skill_program_and_input_hashes_match_the_release(self):
        for record in [self.manifest["skill"], self.manifest["input"], *self.manifest["programs"]]:
            digest = hashlib.sha256(release_bytes(record["path"])).hexdigest()
            self.assertEqual(digest, record["sha256"], record["path"])
        self.assertEqual(self.manifest["input"]["provenance"], "synthetic")
        self.assertIn(b"Synthetic example", release_bytes(self.manifest["input"]["path"]))

    def test_recorded_runs_used_the_released_skill(self):
        """The skill directory at the input commit equals the one released."""
        commit = self.manifest["input_commit"]
        if git("cat-file", "-e", commit + "^{commit}").returncode != 0:
            self.skipTest("input commit not in this clone")
        released = release_ref() or "HEAD"
        for path in ("skills/" + NAME, self.manifest["input"]["path"]):
            at_input = git("rev-parse", commit + ":" + path).stdout.strip()
            at_release = git("rev-parse", released + ":" + path).stdout.strip()
            self.assertEqual(at_input, at_release, path)

    def test_both_clients_ran_and_left_the_source_unchanged(self):
        runs = self.manifest["invocations"]
        self.assertEqual(sorted(run["product"] for run in runs), ["Claude Code", "Codex"])
        for run in runs:
            self.assertEqual(run["source_after_run_sha256"], self.manifest["input"]["sha256"], run["product"])

    def test_prompt_and_version_files_back_the_transcripts(self):
        """The raw streams echo neither, so both are committed as captured."""
        for run in self.manifest["invocations"]:
            prompt = (ROOT / run["prompt_file"]["path"]).read_text(encoding="utf-8").strip()
            version = (ROOT / run["version_file"]["path"]).read_text(encoding="utf-8").strip()
            transcript = (ROOT / run["transcript"]["path"]).read_text(encoding="utf-8")
            self.assertEqual(prompt, run["invocation"])
            self.assertIn("== prompt ==\n" + prompt + "\n", transcript)
            self.assertEqual(version, run["version"])

    def test_transcript_and_output_hashes(self):
        for run in self.manifest["invocations"]:
            for key in ("transcript", "output", "prompt_file", "version_file"):
                self.assertEqual(sha256(run[key]["path"]), run[key]["sha256"], run[key]["path"])
            self.assertTrue(run["output"]["path"].endswith("/weekly-update.50per.md"))
            self.assertEqual(sha256(run["renderer"]["path"]), run["renderer"]["sha256"])

    def test_transcripts_name_no_machine(self):
        for path in sorted((ROOT / "evidence").rglob("*")):
            if not path.is_file() or path.suffix not in (".txt", ".md", ".json"):
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in (r"/home/[a-z]", r"/Users/[A-Za-z]", r"[A-Z]:\\+Users",r"/mnt/[a-z]/"):
                self.assertNotRegex(text, pattern, f"{path.name}: {pattern}")

    def test_transcripts_show_the_skill_and_the_verifier(self):
        for run in self.manifest["invocations"]:
            text = (ROOT / run["transcript"]["path"]).read_text(encoding="utf-8")
            self.assertIn(run["invocation"], text)
            self.assertIn("verify_reduction.py", text)
            self.assertIn("valid=True", text)
            self.assertIn("ordered_lexical_subsequence=True", text)

    def test_outputs_are_deletion_only_copies(self):
        source = release_text(self.manifest["input"]["path"])
        verify = release_verifier()
        for run in self.manifest["invocations"]:
            copy = (ROOT / run["output"]["path"]).read_text(encoding="utf-8")
            report = verify.analyze_reduction(source, copy, Decimal("1"), False, False)
            self.assertTrue(report["valid"], (run["product"], report["issues"]))
            self.assertEqual(envelope(copy), envelope(source), run["product"])

    def test_every_unit_meets_its_floor(self):
        rows = results(self.manifest)
        self.assertEqual(len(rows), 6)
        for product, unit, report in rows:
            if report["valid"] is None:
                continue
            self.assertTrue(report["valid"], (product, unit, report["issues"]))
            self.assertEqual(report["target_words"], math.ceil(report["source_words"] / 2))
            self.assertLess(report["candidate_words"], report["source_words"])


class AssetTest(unittest.TestCase):
    def test_social_preview_is_1280_by_640(self):
        data = (ROOT / "assets" / "social-preview.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (1280, 640))

    def test_social_preview_stamp_binds_source_and_render(self):
        stamp = (ROOT / "assets" / "social-preview.sha256").read_text().split()
        self.assertEqual(stamp, [sha256("assets/build.py"), sha256("assets/social-preview.png")])

    def test_demo_loops_and_poster_is_static(self):
        demo = (ROOT / "assets" / "demo.svg").read_text(encoding="utf-8")
        poster = (ROOT / "assets" / "poster.svg").read_text(encoding="utf-8")
        self.assertIn('repeatCount="indefinite"', demo)
        self.assertNotIn("<animate", poster)
        self.assertIn('text-decoration="line-through"', poster)

    def test_demo_and_poster_rebuild_from_the_evidence(self):
        for name, data in BUILD.demo_svgs().items():
            self.assertEqual((ROOT / "assets" / name).read_bytes(), data, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
