from __future__ import annotations

from .errors import JupyagentError
from .selectors import resolve_selector_index


def resolve_insert_position(cells: list[dict], position: str) -> int:
    if position == "start":
        return 0
    if position == "end":
        return len(cells)
    if position.startswith("before:"):
        selector = position.removeprefix("before:")
        return resolve_selector_index(cells, selector)
    if position.startswith("after:"):
        selector = position.removeprefix("after:")
        return resolve_selector_index(cells, selector) + 1
    raise JupyagentError(f"error: position '{position}' is invalid")


def resolve_move_position(cells: list[dict], selected_indices: list[int], position: str) -> int:
    if position == "start":
        return 0
    if position == "end":
        return len(cells) - len(selected_indices)

    relation: str
    selector: str
    if position.startswith("before:"):
        relation = "before"
        selector = position.removeprefix("before:")
    elif position.startswith("after:"):
        relation = "after"
        selector = position.removeprefix("after:")
    else:
        raise JupyagentError(f"error: position '{position}' is invalid")

    anchor = resolve_selector_index(cells, selector)
    if anchor in selected_indices:
        raise JupyagentError("error: move position cannot target a selected cell")
    base_index = anchor if relation == "before" else anchor + 1
    removed_before = sum(1 for index in selected_indices if index < base_index)
    return base_index - removed_before
