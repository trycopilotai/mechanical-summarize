#!/usr/bin/env python3
"""Build the README demo, its poster, and the social preview.

    python3 assets/build.py           # write assets/*
    python3 assets/build.py --check   # rebuild in memory, fail on drift

demo.svg and poster.svg are reconstructed with the standard library
from three evidence files: the synthetic input, the copy Claude Code
wrote, and the prompt in the Claude Code transcript. They show the
input's first unit with every deleted word struck through, the copy
of that unit, and the verifier's result for it. Words are matched
the way the verifier matches them, to the earliest source token, so
where a word repeats the struck copy may be the other one. demo.svg
reveals the frames in order and loops; poster.svg is the last frame,
for reduced motion. social-preview.png (1280 by 640) needs Pillow and
the DejaVu Sans Mono font; social-preview.sha256 records the SHA-256
of this file and of the PNG.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import sys
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SOURCE = ROOT / "examples" / "weekly-update.md"
COPY = ROOT / "evidence" / "outputs" / "claude-code" / "weekly-update.50per.md"
TRANSCRIPT = ROOT / "evidence" / "transcripts" / "claude-code-invocation.txt"
VERIFIER = ROOT / "skills" / "mechanical-summarize" / "scripts" / "verify_reduction.py"
NAME = "mechanical-summarize"
CLAIM = "Shorten prose to a word budget by deleting, never rewriting."
RETAIN = Decimal("0.5")
FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/Library/Fonts/DejaVuSansMono.ttf",
]

WIDTH, LINE, PAD, WRAP = 920, 22, 20, 100
DURATION = 12.0
BG, FG, DIM, DEL, OK = "#0d1117", "#e6edf3", "#8b949e", "#f85149", "#3fb950"


def verifier():
    spec = importlib.util.spec_from_file_location("verify_reduction", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def units(text: str) -> list:
    """Return (heading, body) for every second-level section."""
    sections, heading, body = [], None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading is not None:
                sections.append((heading, "\n".join(body).strip()))
            heading, body = line[3:], []
        elif heading is not None:
            body.append(line)
    if heading is not None:
        sections.append((heading, "\n".join(body).strip()))
    return sections


def marked_words(source: str, copy: str, module) -> list:
    """Mark each source word kept or deleted, matching like the verifier."""
    wanted = [token.casefold() for token in module.lexical_tokens(copy)]
    cursor, marked = 0, []
    for word in source.split():
        kept = False
        for token in module.lexical_tokens(word):
            if cursor < len(wanted) and token.casefold() == wanted[cursor]:
                cursor += 1
                kept = True
        marked.append((word, kept))
    if cursor != len(wanted):
        raise SystemExit("the copy is not an ordered subsequence of the source")
    return marked


def wrap(words: list, width: int) -> list:
    lines, current, used = [], [], 0
    for word, kept in words:
        extra = len(word) + (1 if current else 0)
        if current and used + extra > width:
            lines.append(current)
            current, used = [], 0
            extra = len(word)
        current.append((word, kept))
        used += extra
    if current:
        lines.append(current)
    return lines


def prompt_lines() -> list:
    text = TRANSCRIPT.read_text(encoding="utf-8")
    prompt = text.split("== prompt ==\n", 1)[1].split("\n\n", 1)[0].strip()
    words = [(word, True) for word in ("$ claude -p '%s'" % prompt).split()]
    lines = [" ".join(word for word, _kept in line) for line in wrap(words, WRAP - 2)]
    return [[(line if index == 0 else "  " + line, DIM, False)] for index, line in enumerate(lines)]


def frames() -> dict:
    """Compute every line of the demo, grouped by the frame that reveals it."""
    module = verifier()
    source_units = units(SOURCE.read_text(encoding="utf-8"))
    copy_units = units(COPY.read_text(encoding="utf-8"))
    heading, source_body = source_units[0]
    copy_heading, copy_body = copy_units[0]
    if copy_heading != heading:
        raise SystemExit("the copy changed the first heading")
    words = marked_words(source_body, copy_body, module)
    report = module.analyze_reduction(source_body, copy_body, RETAIN, True, False)
    verdict = "valid" if report["valid"] else "INVALID"
    copy_words = [(word, True) for word in copy_body.split()]
    return {
        "intro": [[("# reconstructed from evidence/, not recorded; flags omitted, see evidence/manifest.json", DIM, False)]]
        + prompt_lines()
        + [[], [("## %s (source)" % heading, DIM, False)]],
        "plain": [[(word, FG, False) for word, _kept in line] for line in wrap(words, WRAP)],
        "marked": [
            [(word, FG if kept else DEL, not kept) for word, kept in line]
            for line in wrap(words, WRAP)
        ],
        "copy": [[], [("## %s (the copy Claude Code wrote)" % copy_heading, DIM, False)]]
        + [[(word, FG, False) for word, _kept in line] for line in wrap(copy_words, WRAP)],
        "result": [
            [],
            [("verify_reduction.py on this section and its copy, --retain 0.5 (summary):", DIM, False)],
            [
                (
                    "%s: %d words -> %d, floor %d, %.1f%% retained, ordered subsequence: %s"
                    % (
                        verdict,
                        report["source_words"],
                        report["candidate_words"],
                        report["target_words"],
                        report["retained_percent"],
                        "yes" if report["ordered_lexical_subsequence"] else "no",
                    ),
                    OK if report["valid"] else DEL,
                    False,
                )
            ],
        ],
    }


def text_line(spans: list, y: int) -> str:
    parts = []
    for index, (word, color, struck) in enumerate(spans):
        decoration = ' text-decoration="line-through"' if struck else ""
        space = " " if index else ""
        parts.append('%s<tspan fill="%s"%s>%s</tspan>' % (space, color, decoration, escape(word)))
    return '<text x="%d" y="%d" xml:space="preserve">%s</text>' % (PAD, y, "".join(parts))


def group(lines: list, first_row: int, shown: tuple) -> list:
    """Render rows; shown is None (always) or opacity values and key times."""
    body = [text_line(spans, PAD + LINE * (first_row + index + 1) - 6) for index, spans in enumerate(lines) if spans]
    if shown is None:
        return body
    values, times = shown
    animate = (
        '<animate attributeName="opacity" dur="%.1fs" repeatCount="indefinite" '
        'calcMode="discrete" values="%s" keyTimes="%s"/>' % (DURATION, values, times)
    )
    return ['<g opacity="%s">' % values.split(";")[0], animate] + body + ["</g>"]


def svg(animate: bool) -> str:
    parts = frames()
    rows = len(parts["intro"]) + len(parts["marked"]) + len(parts["copy"]) + len(parts["result"])
    height = PAD * 2 + LINE * rows
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
        'font-family="DejaVu Sans Mono, Menlo, Consolas, monospace" font-size="14">' % (WIDTH, height, WIDTH, height),
        '<rect width="100%%" height="100%%" rx="8" fill="%s"/>' % BG,
    ]
    row = 0
    out += group(parts["intro"], row, None)
    row += len(parts["intro"])
    if animate:
        # Cumulative: the plain unit gives way to the same words marked,
        # then the copy and the verdict are added below and stay.
        out += group(parts["plain"], row, ("1;0;0", "0;0.25;1"))
        out += group(parts["marked"], row, ("0;1;1", "0;0.25;1"))
        row += len(parts["marked"])
        out += group(parts["copy"], row, ("0;1;1", "0;0.5;1"))
        row += len(parts["copy"])
        out += group(parts["result"], row, ("0;1;1", "0;0.7;1"))
    else:
        out += group(parts["marked"], row, None)
        row += len(parts["marked"])
        out += group(parts["copy"], row, None)
        row += len(parts["copy"])
        out += group(parts["result"], row, None)
    out.append("</svg>\n")
    return "\n".join(out)


def demo_svgs() -> dict:
    return {"demo.svg": svg(animate=True).encode(), "poster.svg": svg(animate=False).encode()}


def social_preview() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    font_path = next((p for p in FONTS if Path(p).is_file()), None)
    if font_path is None:
        raise SystemExit("DejaVu Sans Mono not found; install fonts-dejavu")
    module = verifier()
    _heading, source_body = units(SOURCE.read_text(encoding="utf-8"))[0]
    _heading, copy_body = units(COPY.read_text(encoding="utf-8"))[0]
    words = marked_words(source_body, copy_body, module)
    image = Image.new("RGB", (1280, 640), BG)
    draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(font_path, 72)
    body = ImageFont.truetype(font_path, 30)
    small = ImageFont.truetype(font_path, 26)
    draw.text((80, 90), NAME, font=title, fill=FG)
    draw.text((80, 210), CLAIM, font=body, fill=FG)
    space = draw.textlength(" ", font=body)
    for index, line in enumerate(wrap(words, 58)[:3]):
        x, y = 80.0, 310 + index * 52
        for word, kept in line:
            width = draw.textlength(word, font=body)
            draw.text((x, y), word, font=body, fill=FG if kept else DEL)
            if not kept:
                draw.line((x, y + 19, x + width, y + 19), fill=DEL, width=3)
            x += width + space
    draw.text((80, 540), "github.com/trycopilotai/" + NAME, font=small, fill=DIM)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def build() -> dict:
    outputs = demo_svgs()
    png = social_preview()
    stamp = "%s %s\n" % (
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        hashlib.sha256(png).hexdigest(),
    )
    outputs["social-preview.png"] = png
    outputs["social-preview.sha256"] = stamp.encode()
    return outputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    outputs = build()
    drift = []
    for name, data in outputs.items():
        path = ASSETS / name
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                drift.append(name)
        else:
            path.write_bytes(data)
    if drift:
        print("assets differ from a rebuild: " + ", ".join(drift), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
