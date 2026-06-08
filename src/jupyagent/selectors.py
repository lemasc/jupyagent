from __future__ import annotations

import re

from .errors import JupyagentError

RANGE_PATTERN = re.compile(r"^(\d+):(\d+)$")


def resolve_selector_indices(cells: list[dict], selector: str) -> list[int]:
    ids = [cell.get("id") for cell in cells]
    if selector == "all":
        return list(range(len(cells)))
    if selector in ids:
        return [index for index, cell_id in enumerate(ids) if cell_id == selector]
    match = RANGE_PATTERN.fullmatch(selector)
    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        if start < 1 or end < start or end > len(cells):
            raise JupyagentError(f"error: selector '{selector}' is invalid")
        return list(range(start - 1, end))
    if selector.isdigit():
        index = int(selector)
        if index < 1 or index > len(cells):
            raise JupyagentError(f"error: selector '{selector}' did not match any cell")
        return [index - 1]
    raise JupyagentError(f"error: selector '{selector}' did not match any cell")


def resolve_selector_index(cells: list[dict], selector: str) -> int:
    indices = resolve_selector_indices(cells, selector)
    if len(indices) != 1:
        raise JupyagentError(
            f"error: selector '{selector}' matched multiple cells where one is required"
        )
    return indices[0]
