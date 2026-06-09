from __future__ import annotations

import shutil
from pathlib import Path

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
