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
