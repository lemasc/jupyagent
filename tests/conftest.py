from __future__ import annotations

import shutil
from pathlib import Path

import nbformat
import pytest


@pytest.fixture
def notebook_copy(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "sample.ipynb"
    target = tmp_path / "sample.ipynb"
    shutil.copy2(source, target)
    return target


@pytest.fixture
def exec_success_notebook(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "exec_success.ipynb"
    target = tmp_path / "exec_success.ipynb"
    shutil.copy2(source, target)
    return target


@pytest.fixture
def exec_failure_notebook(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "exec_failure.ipynb"
    target = tmp_path / "exec_failure.ipynb"
    shutil.copy2(source, target)
    return target


@pytest.fixture
def exec_timeout_notebook(tmp_path: Path) -> Path:
    target = tmp_path / "exec_timeout.ipynb"
    notebook = nbformat.v4.new_notebook()
    notebook.cells = [
        nbformat.v4.new_code_cell(
            source="import time\ntime.sleep(2)\n",
            id="slow",
        )
    ]
    notebook.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook.metadata["language_info"] = {"name": "python"}
    nbformat.write(notebook, target)
    return target
