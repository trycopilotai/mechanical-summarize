# Contributing

This repository is one skill, its verifier, the verifier's
tests, and the scripts that render the evidence and build
the demo images.

## Run the checks first

```sh
make check
```

That runs `tests/test_verify_reduction.py`,
`tests/test_verify_cli.py`, and
`tests/test_integrations.py`. They need `make`, Python 3.9
or later, and `git`; no Python package is installed. The
packaging contract needs a git clone, because it reads
`git log`; its release-tag test skips when `HEAD` carries no
tag.

**The packaging contract asserts on the README.** These fail
on an innocent-looking prose edit:

- the claim line directly under the README's title must
  appear verbatim;
- the line `**Not measured, stated up front.**` must come
  before `## What it does`;
- each install block must carry its own `release=` pin at
  the version both plugin manifests ship, and its
  `install_target=` and `cp -R` lines must keep their exact
  form;
- the four invocation forms must each appear in backticks;
- the results table must match what the verifier computes
  for the recorded outputs;
- `SKILL.md` must stay under 500 lines with `name` and
  `description` as its only frontmatter keys, and keep its
  three `python3 <skill-dir>/scripts/verify_reduction.py`
  command lines (change the test if you add one);
- both Codex default prompts must name their invocation form
  and stay within 128 characters;
- `SECURITY.md` must keep its advisory link, this file must
  mention `make check`, and `LICENSE` must start with
  `MIT License`;
- every relative link in the README must resolve;
- `assets/demo.svg` and `assets/poster.svg` must equal a
  fresh rebuild from the evidence.

`skill` at the repository root is a symlink to
`skills/mechanical-summarize/`, kept for tools that look for
a root `skill/` directory. Git for Windows checks it out as
a plain file unless `core.symlinks` is on, and the packaging
contract then fails. On Windows, clone with
`git clone -c core.symlinks=true` (which needs Developer
Mode or an elevated shell) or run the checks under WSL.

`make asset-check` rebuilds every image, the social preview
included, and fails when a committed one differs. It needs
Pillow and the DejaVu Sans Mono font, and the PNG's bytes
depend on the Pillow version; CI does not run it.

## Where to start

Issues labelled
[good first issue](https://github.com/trycopilotai/mechanical-summarize/labels/good%20first%20issue)
are small and self-contained. Issues labelled
[help wanted](https://github.com/trycopilotai/mechanical-summarize/labels/help%20wanted)
need a design decision first, so comment before you start.

## Changes

- Keep the skill deletion-only. A change that lets the agent
  add, substitute, or reorder words is out of scope here.
- Do not edit files under `evidence/` by hand. They are
  recorded agent runs, and `evidence/manifest.json` records
  their hashes and every transform applied to them.
- You can change the skill and the verifier without
  re-recording those runs. The evidence tests read the
  skill, the verifier, and the input from the release tag
  named in `evidence/manifest.json`, and the history test
  checks only that tag's commits, so a `Co-authored-by`
  trailer in your commits is fine. In a fork, fetch the tag
  from this repository first: add it once with
  `git remote add upstream https://github.com/trycopilotai/mechanical-summarize`,
  then run `git fetch upstream --tags`. Without the tag,
  those tests fall back to your working tree.
- Treat `examples/weekly-update.md` as the recorded input
  and leave it as it is; add new examples beside it.
- Three evidence checks still follow your working tree,
  besides the packaging checks on the skill itself.
  `assets/demo.svg` and `assets/poster.svg` must equal a
  rebuild, so run `make assets` after changing the verifier
  or `assets/build.py`; `make assets` always needs Pillow
  and the DejaVu Sans Mono font, because it also builds the
  social preview. The social preview's stamp binds
  `assets/build.py`. `scripts/render_invocation.py` is
  pinned by hash, because the committed transcripts were
  rendered with it. A new release records new runs.
- `examples/weekly-update.md` is synthetic. Keep examples
  synthetic or public domain, and say which in the file.
- Prose wraps at 60 columns.
