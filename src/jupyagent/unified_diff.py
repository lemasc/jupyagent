from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import JupyagentError

HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class HunkLine:
    operation: str
    text: str


@dataclass
class Hunk:
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[HunkLine]


@dataclass
class FilePatch:
    path: str
    hunks: list[Hunk]


def parse_unified_diff(patch_text: str) -> list[FilePatch]:
    lines = patch_text.splitlines(keepends=True)
    if not lines:
        raise JupyagentError("error: patch input is empty")
    index = 0
    patches: list[FilePatch] = []
    while index < len(lines):
        if not lines[index].startswith("--- "):
            raise JupyagentError("error: expected '---' file header in patch")
        old_path = _normalize_patch_path(lines[index][4:])
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            raise JupyagentError("error: expected '+++' file header in patch")
        new_path = _normalize_patch_path(lines[index][4:])
        index += 1
        if old_path != new_path:
            raise JupyagentError("error: patch cannot rename virtual cell files")
        hunks: list[Hunk] = []
        while index < len(lines) and not lines[index].startswith("--- "):
            if not lines[index].startswith("@@ "):
                raise JupyagentError("error: expected '@@' hunk header in patch")
            hunk, index = _parse_hunk(lines, index)
            hunks.append(hunk)
        if not hunks:
            raise JupyagentError(f"error: patch for '{old_path}' does not contain any hunks")
        patches.append(FilePatch(path=old_path, hunks=hunks))
    return patches


def apply_unified_diff(source: str, hunks: list[Hunk], target_path: str) -> str:
    original_lines = source.splitlines(keepends=True)
    result: list[str] = []
    cursor = 0
    for hunk in hunks:
        start = max(hunk.old_start - 1, 0)
        if start < cursor or start > len(original_lines):
            raise JupyagentError(_format_hunk_error(target_path, hunk, start + 1, None, None, "patch hunk location is invalid"))
        result.extend(original_lines[cursor:start])
        cursor = start
        old_seen = 0
        new_seen = 0
        for line in hunk.lines:
            if line.operation == " ":
                _expect_source_line(original_lines, cursor, line.text, target_path, hunk, "context")
                result.append(line.text)
                cursor += 1
                old_seen += 1
                new_seen += 1
                continue
            if line.operation == "-":
                _expect_source_line(original_lines, cursor, line.text, target_path, hunk, "delete")
                cursor += 1
                old_seen += 1
                continue
            result.append(line.text)
            new_seen += 1
        if old_seen != hunk.old_count or new_seen != hunk.new_count:
            raise JupyagentError("error: patch hunk line counts do not match header")
    result.extend(original_lines[cursor:])
    return "".join(result)


def _parse_hunk(lines: list[str], index: int) -> tuple[Hunk, int]:
    header = lines[index].rstrip("\n")
    match = HUNK_HEADER_RE.match(lines[index])
    if not match:
        raise JupyagentError("error: invalid patch hunk header")
    old_start = int(match.group(1))
    new_start = int(match.group(3))
    index += 1
    hunk_lines: list[HunkLine] = []
    while index < len(lines) and not lines[index].startswith(("@@ ", "--- ")):
        raw_line = lines[index]
        if raw_line.startswith("\\ No newline at end of file"):
            if not hunk_lines:
                raise JupyagentError("error: invalid no-newline marker in patch")
            hunk_lines[-1].text = hunk_lines[-1].text.rstrip("\n")
            index += 1
            continue
        operation = raw_line[:1]
        if operation not in {" ", "+", "-"}:
            raise JupyagentError("error: invalid patch hunk line")
        hunk_lines.append(HunkLine(operation=operation, text=raw_line[1:]))
        index += 1
    old_count = sum(1 for line in hunk_lines if line.operation != "+")
    new_count = sum(1 for line in hunk_lines if line.operation != "-")
    return Hunk(header, old_start, old_count, new_start, new_count, hunk_lines), index


def _normalize_patch_path(value: str) -> str:
    path = value.rstrip("\n").split("\t", 1)[0].strip()
    if path in {"", "/dev/null"}:
        raise JupyagentError("error: patch must target existing virtual cell files")
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _expect_source_line(
    source_lines: list[str],
    index: int,
    expected: str,
    target_path: str,
    hunk: Hunk,
    line_kind: str,
) -> None:
    actual = source_lines[index] if index < len(source_lines) else None
    if actual != expected:
        raise JupyagentError(
            _format_hunk_error(target_path, hunk, index + 1, actual, expected, "patch hunk did not match cell source", line_kind)
        )


def _format_hunk_error(
    target_path: str,
    hunk: Hunk,
    source_line: int,
    actual: str | None,
    patch_text: str | None,
    summary: str,
    line_kind: str | None = None,
) -> str:
    lines = [
        f"error: {summary}",
        f"target: {target_path}",
        f"hunk: {hunk.header}",
        f"source_line: {source_line}",
    ]
    if actual is not None:
        lines.append(f"source: {actual!r}")
    else:
        lines.append("source: <end of file>")
    if patch_text is not None:
        label = "patch"
        if line_kind == "context":
            label = "patch_context"
        elif line_kind == "delete":
            label = "patch_delete"
        lines.append(f"{label}: {patch_text!r}")
    hint = _hint_for_mismatch(actual, patch_text)
    if hint:
        lines.append(f"hint: {hint}")
    return "\n".join(lines)


def _hint_for_mismatch(actual: str | None, patch_text: str | None) -> str | None:
    if actual is None:
        return "patch may be stale against the current notebook source"
    if patch_text is None:
        return None
    if patch_text[:1] == " " and actual[:1] in {"-", "+"}:
        return "patch content lines that begin with '+' or '-' must include that character after the diff marker as well"
    if patch_text[:1] in {"-", "+"} and actual[:1] == " ":
        return "patch content may include a duplicated leading '+' or '-' character that is not present in the notebook source"
    return "patch may be stale against the current notebook source"
