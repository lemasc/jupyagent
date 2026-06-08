from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import nbformat
from typer.testing import CliRunner

from jupyagent.cli import app

runner = CliRunner()


def test_cell_list_warns_for_duplicate_ids(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "list", str(notebook_copy)])
    assert result.exit_code == 0
    assert "| 1 | intro | markdown | # Title |" in result.stdout
    assert "warning: detected 1 cell id issue" in result.stderr


def test_cell_read_range(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "read", str(notebook_copy), "2:3"])
    assert result.exit_code == 0
    assert "<!-- cell id: code-1 -->" in result.stdout
    assert "```python" in result.stdout
    assert "<!-- cell id: code-1 -->" in result.stdout


def test_cell_insert_repairs_ids(notebook_copy: Path) -> None:
    result = runner.invoke(
        app,
        ["cell", "insert", str(notebook_copy), "after:intro", "--type", "markdown"],
        input="Inserted text\n",
    )
    assert result.exit_code == 0
    assert "operation: cell insert" in result.stdout
    assert "ids_repaired: 1" in result.stdout

    notebook = nbformat.read(notebook_copy, as_version=4)
    ids = [cell["id"] for cell in notebook.cells]
    assert len(ids) == len(set(ids))
    assert notebook.cells[1]["source"] == "Inserted text\n"


def test_cell_replace_clears_outputs_by_default(notebook_copy: Path) -> None:
    result = runner.invoke(
        app,
        ["cell", "replace", str(notebook_copy), "2", "--type", "code"],
        input="print('changed')\n",
    )
    assert result.exit_code == 0
    assert "outputs_cleared: true" in result.stdout

    notebook = nbformat.read(notebook_copy, as_version=4)
    cell = notebook.cells[1]
    assert cell["source"] == "print('changed')\n"
    assert cell["outputs"] == []
    assert cell["execution_count"] is None


def test_cell_delete_range(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "delete", str(notebook_copy), "2:3"])
    assert result.exit_code == 0
    assert "count: 2" in result.stdout

    notebook = nbformat.read(notebook_copy, as_version=4)
    assert len(notebook.cells) == 1


def test_cell_move_to_end(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "move", str(notebook_copy), "1", "end"])
    assert result.exit_code == 0
    assert "operation: cell move" in result.stdout

    notebook = nbformat.read(notebook_copy, as_version=4)
    assert notebook.cells[-1]["id"] == "intro"


def test_output_read_extracts_image_asset(notebook_copy: Path) -> None:
    notebook = json.loads(notebook_copy.read_text(encoding="utf-8"))
    notebook["cells"][1]["outputs"].append(
        {
            "output_type": "display_data",
            "data": {"image/png": base64.b64encode(b"png-bytes").decode("ascii")},
            "metadata": {},
        }
    )
    notebook_copy.write_text(json.dumps(notebook), encoding="utf-8")

    result = runner.invoke(app, ["output", "read", str(notebook_copy), "code-1"])
    assert result.exit_code == 0
    assert "![output image](.jupyagent/assets/sample/code-1/2.png)" in result.stdout
    assert (notebook_copy.parent / ".jupyagent" / "assets" / "sample" / "code-1" / "2.png").exists()


def test_output_read_converts_html_table_to_markdown(tmp_path: Path) -> None:
    notebook = tmp_path / "pandas.ipynb"
    shutil.copy2(Path(__file__).parent / "fixtures" / "pandas.ipynb", notebook)

    result = runner.invoke(app, ["output", "read", str(notebook), "1"])

    assert result.exit_code == 0
    assert "|  | Name | Age |" in result.stdout
    assert "| --- | --- | --- |" in result.stdout
    assert "| 0 | Alice | 25 |" in result.stdout
    assert "| 1 | Bob | 30 |" in result.stdout
    assert "<table" not in result.stdout


def test_missing_selector_exits_nonzero(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "read", str(notebook_copy), "missing"])
    assert result.exit_code == 1
    assert "did not match any cell" in result.stderr
