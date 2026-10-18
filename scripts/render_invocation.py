#!/usr/bin/env python3
"""Render an agent client's raw JSON-lines output as a readable transcript.

Standard library only. The transcript holds a header, the prompt,
every tool call with its result, and the final message. Each
argument is cut at ARGUMENT_LIMIT characters and each tool result
at RESULT_LIMIT characters.

    python3 scripts/render_invocation.py claude-code RAW PROMPT_FILE \
        --replace OLD=NEW ... > transcript.txt
    python3 scripts/render_invocation.py codex RAW PROMPT_FILE \
        --replace OLD=NEW ... > transcript.txt

The only edits are the declared --replace pairs, applied in the
order given to every rendered string before it is cut. A value
matches anywhere it occurs, so give longer values first.
"""

from __future__ import annotations

import argparse
import json
import sys

ARGUMENT_LIMIT = 4000
RESULT_LIMIT = 1500


def cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + " ...[%d more characters]" % (len(text) - limit)


class Renderer:
    def __init__(self, replacements):
        self.replacements = replacements

    def clean(self, text: str) -> str:
        for old, new in self.replacements:
            text = text.replace(old, new)
        return text

    def field(self, key: str, value, limit: int = ARGUMENT_LIMIT) -> str:
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        return "    %s: %s" % (key, cut(self.clean(value), limit).replace("\n", "\\n"))


def result_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def claude_code(raw: str):
    header, calls, results, final = [], [], {}, ""
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            header.append("client: Claude Code %s" % event.get("claude_code_version", "?"))
            header.append("model: %s" % event.get("model"))
        elif kind == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    calls.append((block.get("id"), block.get("name"), block.get("input") or {}))
        elif kind == "user":
            content = event.get("message", {}).get("content", [])
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    results[block.get("tool_use_id")] = result_text(block.get("content"))
        elif kind == "result":
            final = event.get("result", "")
            header.append("result: %s, %s turns" % (event.get("subtype"), event.get("num_turns")))
    rendered = [(name, arguments, results.get(call_id)) for call_id, name, arguments in calls]
    return header, rendered, final


def codex(raw: str):
    header, calls, final = ["client: Codex"], [], ""
    for line in raw.splitlines():
        if not line.strip() or not line.lstrip().startswith("{"):
            continue
        event = json.loads(line)
        if event.get("type") == "thread.started":
            header.append("thread: started")
        if event.get("type") == "turn.completed":
            header.append("turn: completed")
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        kind = item.get("type")
        if kind == "command_execution":
            arguments = {"command": item.get("command", ""), "exit_code": item.get("exit_code")}
            calls.append(("shell", arguments, item.get("aggregated_output", "")))
        elif kind == "file_change":
            calls.append(("file_change", {"changes": item.get("changes", [])}, None))
        elif kind == "mcp_tool_call":
            calls.append((item.get("tool", "mcp"), item.get("arguments") or {}, None))
        elif kind == "agent_message":
            final = item.get("text", "")
    return header, calls, final


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("client", choices=["claude-code", "codex"])
    parser.add_argument("raw")
    parser.add_argument("prompt")
    parser.add_argument("--replace", action="append", default=[], metavar="OLD=NEW")
    args = parser.parse_args(argv)
    replacements = []
    for pair in args.replace:
        old, sep, new = pair.partition("=")
        if not sep or not old:
            parser.error("--replace needs OLD=NEW")
        replacements.append((old, new))
    render = Renderer(replacements)
    with open(args.raw, encoding="utf-8") as handle:
        raw = handle.read()
    with open(args.prompt, encoding="utf-8") as handle:
        prompt = handle.read().strip()
    header, calls, final = (claude_code if args.client == "claude-code" else codex)(raw)
    out = ["== header =="] + header + ["", "== prompt ==", render.clean(prompt), "", "== tool calls =="]
    for number, (name, arguments, result) in enumerate(calls, 1):
        out.append("%d. %s" % (number, name))
        for key, value in arguments.items():
            out.append(render.field(key, value))
        if result is not None:
            out.append(render.field("result", result, RESULT_LIMIT))
    out += ["", "== final message ==", render.clean(final).rstrip(), ""]
    sys.stdout.write("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
