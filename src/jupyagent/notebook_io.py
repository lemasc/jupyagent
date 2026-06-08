from __future__ import annotations

import json
import tempfile
from pathlib import Path

import nbformat

from .errors import JupyagentError


def load_notebook(path: Path):
    if not path.exists():
        raise JupyagentError(f"error: notebook '{path}' does not exist")
    if not path.is_file():
        raise JupyagentError(f"error: notebook '{path}' is not a file")
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = handle.read()
        if not raw.strip():
            return nbformat.v4.new_notebook()
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JupyagentError(f"error: notebook '{path}' is not valid JSON") from exc
    try:
        notebook = nbformat.from_dict(data)
        if not isinstance(notebook.get("cells"), list):
            raise ValueError("missing cells")
        return notebook
    except Exception as exc:
        raise JupyagentError(f"error: notebook '{path}' is not a valid notebook") from exc


def atomic_write_notebook(path: Path, notebook) -> None:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=path.suffix,
            prefix=f".{path.stem}.",
            dir=path.parent,
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            nbformat.write(notebook, handle)
        tmp_path.replace(path)
    except Exception as exc:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise JupyagentError(f"error: failed to write notebook '{path}' atomically") from exc
