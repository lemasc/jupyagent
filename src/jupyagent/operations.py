from __future__ import annotations

import copy
import re
import sys
import time
from pathlib import Path

import nbformat
import nbclient
import yaml
from jupyter_client.kernelspec import NoSuchKernel
from nbclient.exceptions import CellExecutionError, CellTimeoutError

from .cell_ids import count_id_issues, ensure_cell_ids
from .cell_paths import cell_virtual_path
from .errors import JupyagentError
from .notebook_io import atomic_write_notebook, load_notebook
from .positions import resolve_insert_position, resolve_move_position
from .render_cells import render_cell_list, render_cell_source
from .render_outputs import render_cell_outputs, render_output_body
from .selectors import resolve_selector_index, resolve_selector_indices
from .unified_diff import apply_unified_diff, parse_unified_diff

CELL_TYPES = {"code", "markdown", "raw"}
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def list_cells(notebook_path: Path) -> str:
    notebook = load_notebook(notebook_path)
    _warn_id_issues(notebook.cells)
    return render_cell_list(notebook.cells)


def read_cells(notebook_path: Path, selector: str, include_output: bool = False) -> str:
    notebook = load_notebook(notebook_path)
    _warn_id_issues(notebook.cells)
    indices = resolve_selector_indices(notebook.cells, selector)
    return "\n\n".join(
        _render_cell_read(notebook_path, notebook.cells[index], index + 1, include_output)
        for index in indices
    )


def read_outputs(notebook_path: Path, selector: str) -> str:
    notebook = load_notebook(notebook_path)
    _warn_id_issues(notebook.cells)
    indices = resolve_selector_indices(notebook.cells, selector)
    return "\n\n".join(
        render_cell_outputs(notebook_path, notebook.cells[index], index + 1) for index in indices
    )


def list_cell_paths(notebook_path: Path, selector: str) -> str:
    notebook = load_notebook(notebook_path)
    _warn_id_issues(notebook.cells)
    ensure_cell_ids(notebook.cells)
    indices = resolve_selector_indices(notebook.cells, selector)
    return "\n".join(cell_virtual_path(notebook_path, notebook.cells[index], index + 1) for index in indices)


def _render_cell_read(notebook_path: Path, cell: dict, index: int, include_output: bool) -> str:
    rendered = render_cell_source(cell, index)
    if not include_output:
        return rendered
    return "\n".join([rendered, "", "## Outputs", "", *render_output_body(notebook_path, cell)])


def insert_cell(notebook_path: Path, position: str, cell_type: str, source: str) -> str:
    _validate_cell_type(cell_type)
    notebook = load_notebook(notebook_path)
    insert_at = resolve_insert_position(notebook.cells, position)
    new_cell = _new_cell(cell_type, source)
    notebook.cells.insert(insert_at, new_cell)
    repaired = ensure_cell_ids(notebook.cells)
    atomic_write_notebook(notebook_path, notebook)
    return _yaml(
        {
            "modified": notebook_path.name,
            "operation": "cell insert",
            "cell": {
                "id": new_cell["id"],
                "index": insert_at + 1,
                "type": cell_type,
            },
            "ids_repaired": repaired,
        }
    )


def replace_cell(
    notebook_path: Path,
    selector: str,
    cell_type: str,
    source: str,
    keep_outputs: bool,
) -> str:
    _validate_cell_type(cell_type)
    notebook = load_notebook(notebook_path)
    index = resolve_selector_index(notebook.cells, selector)
    existing = notebook.cells[index]
    notebook.cells[index] = _replacement_cell(existing, cell_type, source, keep_outputs)
    repaired = ensure_cell_ids(notebook.cells)
    atomic_write_notebook(notebook_path, notebook)
    return _yaml(
        {
            "modified": notebook_path.name,
            "operation": "cell replace",
            "cell": {
                "id": notebook.cells[index]["id"],
                "index": index + 1,
                "type": cell_type,
            },
            "outputs_cleared": existing.get("cell_type") == "code" and not keep_outputs,
            "ids_repaired": repaired,
        }
    )


def delete_cells(notebook_path: Path, selector: str) -> str:
    notebook = load_notebook(notebook_path)
    indices = resolve_selector_indices(notebook.cells, selector)
    kept_cells = [cell for index, cell in enumerate(notebook.cells) if index not in set(indices)]
    notebook.cells = kept_cells
    repaired = ensure_cell_ids(notebook.cells)
    atomic_write_notebook(notebook_path, notebook)
    return _yaml(
        {
            "modified": notebook_path.name,
            "operation": "cell delete",
            "deleted": {"count": len(indices)},
            "ids_repaired": repaired,
        }
    )


def move_cells(notebook_path: Path, selector: str, position: str) -> str:
    notebook = load_notebook(notebook_path)
    indices = resolve_selector_indices(notebook.cells, selector)
    moved_cells = [notebook.cells[index] for index in indices]
    target = resolve_move_position(notebook.cells, indices, position)
    remaining = [cell for index, cell in enumerate(notebook.cells) if index not in set(indices)]
    for offset, cell in enumerate(moved_cells):
        remaining.insert(target + offset, cell)
    notebook.cells = remaining
    repaired = ensure_cell_ids(notebook.cells)
    atomic_write_notebook(notebook_path, notebook)
    new_indexes = [index + 1 for index, cell in enumerate(notebook.cells) if cell in moved_cells]
    return _yaml(
        {
            "modified": notebook_path.name,
            "operation": "cell move",
            "moved": {"count": len(indices), "indexes": new_indexes},
            "ids_repaired": repaired,
        }
    )


def patch_cells(notebook_path: Path, patch_text: str) -> str:
    notebook = load_notebook(notebook_path)
    repaired = ensure_cell_ids(notebook.cells)
    file_patches = parse_unified_diff(patch_text)
    cell_by_path = {
        cell_virtual_path(notebook_path, cell, index + 1): (index, cell)
        for index, cell in enumerate(notebook.cells)
    }
    patched_indices: list[int] = []
    outputs_cleared = 0
    for file_patch in file_patches:
        target = cell_by_path.get(file_patch.path)
        if target is None:
            raise JupyagentError(f"error: patch target '{file_patch.path}' did not match any cell")
        index, cell = target
        patched_source = apply_unified_diff(cell.get("source", ""), file_patch.hunks, file_patch.path)
        if patched_source == cell.get("source", ""):
            continue
        cell["source"] = patched_source
        if cell.get("cell_type") == "code":
            if cell.get("outputs"):
                outputs_cleared += 1
            cell["outputs"] = []
            cell["execution_count"] = None
        patched_indices.append(index)
    atomic_write_notebook(notebook_path, notebook)
    return _yaml(
        {
            "modified": notebook_path.name,
            "operation": "cell patch",
            "patched_cells": [
                {
                    "id": notebook.cells[index]["id"],
                    "index": index + 1,
                    "type": notebook.cells[index]["cell_type"],
                }
                for index in patched_indices
            ],
            "outputs_cleared": outputs_cleared,
            "ids_repaired": repaired,
        }
    )


def execute_notebook(notebook_path: Path, timeout: int | None, output_path: Path | None) -> str:
    notebook = load_notebook(notebook_path)
    repaired = ensure_cell_ids(notebook.cells)
    destination = output_path or notebook_path
    started = time.monotonic()
    cells_total = len(notebook.cells)
    active_cell: dict[str, int | str | None] = {"index": None, "id": None}

    def on_cell_execute(cell: dict, cell_index: int) -> None:
        active_cell["index"] = cell_index + 1
        active_cell["id"] = cell.get("id")
        print(
            _progress_message(active_cell["index"], active_cell["id"], cells_total),
            file=sys.stderr,
        )

    client = nbclient.NotebookClient(
        notebook,
        timeout=timeout,
        record_timing=False,
        on_cell_execute=on_cell_execute,
    )
    try:
        client.execute()
    except NoSuchKernel as exc:
        raise JupyagentError(f"error: kernel '{exc.name}' is not installed") from exc
    except (CellExecutionError, CellTimeoutError) as exc:
        atomic_write_notebook(destination, notebook)
        raise JupyagentError(
            _execution_error(notebook, destination, started, repaired, exc, active_cell)
        ) from exc
    except Exception as exc:
        raise JupyagentError(f"error: failed to execute notebook '{notebook_path}'") from exc

    atomic_write_notebook(destination, notebook)
    return _yaml(
        {
            "modified": destination.name,
            "operation": "notebook exec",
            "source": notebook_path.name,
            "executed_cells": sum(1 for cell in notebook.cells if cell.get("cell_type") == "code"),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "ids_repaired": repaired,
        }
    )


def read_source(file_path: Path | None) -> str:
    if file_path is not None:
        try:
            return file_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise JupyagentError(f"error: file '{file_path}' does not exist") from exc
    if sys.stdin.isatty():
        raise JupyagentError("error: required stdin input is missing")
    return sys.stdin.read()


def _validate_cell_type(cell_type: str) -> None:
    if cell_type not in CELL_TYPES:
        raise JupyagentError(f"error: unsupported cell type '{cell_type}'")


def _warn_id_issues(cells: list[dict]) -> None:
    issues = count_id_issues(cells)
    if issues:
        suffix = "s" if issues != 1 else ""
        print(f"warning: detected {issues} cell id issue{suffix}", file=sys.stderr)


def _new_cell(cell_type: str, source: str):
    if cell_type == "code":
        return nbformat.v4.new_code_cell(source=source)
    if cell_type == "markdown":
        return nbformat.v4.new_markdown_cell(source=source)
    return nbformat.v4.new_raw_cell(source=source)


def _replacement_cell(existing: dict, cell_type: str, source: str, keep_outputs: bool):
    metadata = copy.deepcopy(existing.get("metadata", {}))
    replacement = _new_cell(cell_type, source)
    replacement["metadata"] = metadata
    replacement["id"] = existing.get("id")
    if cell_type == "code" and keep_outputs and existing.get("cell_type") == "code":
        replacement["outputs"] = copy.deepcopy(existing.get("outputs", []))
        replacement["execution_count"] = existing.get("execution_count")
    return replacement


def _execution_error(
    notebook: dict,
    destination: Path,
    started: float,
    repaired: int,
    exc: CellExecutionError | CellTimeoutError,
    active_cell: dict[str, int | str | None],
) -> str:
    index, cell_id = _resolve_failed_cell(notebook, exc, active_cell)
    payload = {
        "modified": destination.name,
        "operation": "notebook exec",
        "status": "failed",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "ids_repaired": repaired,
        "failed_cell": {"index": index, "id": cell_id},
        "error": _summarize_execution_exception(exc),
    }
    return _yaml(payload)


def _resolve_failed_cell(
    notebook: dict,
    exc: CellExecutionError | CellTimeoutError,
    active_cell: dict[str, int | str | None],
) -> tuple[int | None, str | None]:
    if isinstance(exc, CellTimeoutError) and active_cell["index"] is not None:
        return active_cell["index"], active_cell["id"]
    return _find_failed_cell(notebook)


def _find_failed_cell(notebook: dict) -> tuple[int | None, str | None]:
    for index in range(len(notebook.cells) - 1, -1, -1):
        cell = notebook.cells[index]
        if cell.get("cell_type") != "code":
            continue
        outputs = cell.get("outputs", [])
        if any(output.get("output_type") == "error" for output in outputs):
            return index + 1, cell.get("id")
    return None, None


def _summarize_execution_exception(exc: CellExecutionError | CellTimeoutError) -> str:
    if isinstance(exc, CellTimeoutError):
        return _summarize_timeout_exception(exc)
    lines = [_strip_ansi(line.strip()) for line in str(exc).splitlines() if line.strip()]
    return lines[-1] if lines else exc.__class__.__name__


def _summarize_timeout_exception(exc: CellTimeoutError) -> str:
    text = _strip_ansi(str(exc))
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    match = re.search(r"after\s+(\d+)\s+seconds", first_line)
    if match:
        return f"cell timed out after {match.group(1)} seconds"
    return first_line or exc.__class__.__name__


def _progress_message(index: int | None, cell_id: str | None, total: int) -> str:
    return f"progress: executing cell {index}/{total} (id: {cell_id or 'unknown'})"


def _cell_has_source(cell: dict) -> bool:
    source = cell.get("source", "")
    if isinstance(source, list):
        return bool("".join(source).strip())
    return bool(str(source).strip())


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def _yaml(payload: dict) -> str:
    return yaml.safe_dump(payload, sort_keys=False).rstrip()
