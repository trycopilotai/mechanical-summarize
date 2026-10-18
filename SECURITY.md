# Security

## Reporting a vulnerability

Report privately through GitHub:
<https://github.com/trycopilotai/mechanical-summarize/security/advisories/new>

That opens a private security advisory visible only to the
maintainers. Do not put the details of a vulnerability in a
public issue.

If that link shows "Not Found", private reporting is not
turned on for this repository. Open a public issue titled
"Security report waiting" that says only that you have a
report, with no details, and a maintainer will arrange a
private channel.

## What is in scope

- **Prompt content that redirects an agent.** `SKILL.md` and
  `references/method.md` are instructions an agent follows
  on a user's machine. The documented workflow reads the
  source, writes one copy beside it, writes each section to
  a scratch file in a fresh temporary directory that it
  then deletes, and runs the bundled verifier. Text that
  makes an agent change the source, write outside the copy
  and that temporary directory, or report a reduction it did
  not verify is a valid report, and so is text inside the
  document being shortened that does the same. A choice an
  agent makes that the skill's text did not cause, such as
  an extra scratch file of its own, is not.
- **`verify_reduction.py`.** It reads the one or two UTF-8
  files named on its command line and prints a report. It
  writes no file and opens no network connection. Input
  that makes it write, read a file it was not given, or
  report `valid=True` for a copy that adds or reorders a
  lexical token is in scope.
- **The install blocks.** Each runs `dirname` on its target,
  creates its skills directory under `$HOME`
  (`~/.claude/skills/` or `~/.agents/skills/`) with
  `mkdir -p` if it is missing, then runs `mktemp -d`,
  `git clone`, `mkdir -p`, `cp`, `mv`, and `rm -rf` inside
  it. A state
  that makes either block write or delete outside that
  skills directory is in scope.

## Out of scope

- Meaning lost at a deletion seam that the verifier passes.
  The verifier checks deletion shape and word count only,
  and the README says so. Report it as an ordinary issue.
- Vulnerabilities in Claude Code or Codex themselves. Report
  those to their maintainers.
