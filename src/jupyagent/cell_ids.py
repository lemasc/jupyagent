from __future__ import annotations

import uuid


def _cell_id(cell: dict) -> str | None:
    cell_id = cell.get("id")
    return cell_id if isinstance(cell_id, str) and cell_id else None


def count_id_issues(cells: list[dict]) -> int:
    seen: set[str] = set()
    issues = 0
    for cell in cells:
        cell_id = _cell_id(cell)
        if cell_id is None or cell_id in seen:
            issues += 1
            continue
        seen.add(cell_id)
    return issues


def ensure_cell_ids(cells: list[dict]) -> int:
    seen: set[str] = set()
    repaired = 0
    for cell in cells:
        cell_id = _cell_id(cell)
        if cell_id is None or cell_id in seen:
            repaired += 1
            cell["id"] = _new_id(seen)
            seen.add(cell["id"])
            continue
        seen.add(cell_id)
    return repaired


def _new_id(seen: set[str]) -> str:
    while True:
        value = uuid.uuid4().hex[:8]
        if value not in seen:
            return value
