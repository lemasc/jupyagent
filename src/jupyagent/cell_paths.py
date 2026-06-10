from __future__ import annotations

from pathlib import Path


def cell_virtual_path(notebook_path: Path, cell: dict, index: int) -> str:
    return (
        f"{notebook_path.name}/cells/{index:04d}__{cell.get('id', '')}.source."
        f"{_cell_source_extension(cell.get('cell_type', ''))}"
    )


def _cell_source_extension(cell_type: str) -> str:
    if cell_type == "code":
        return "code"
    if cell_type == "markdown":
        return "md"
    return "raw"
