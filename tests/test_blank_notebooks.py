from __future__ import annotations

import nbformat
from typer.testing import CliRunner

from jupyagent.cli import app

runner = CliRunner()


def test_cell_list_on_blank_file(tmp_path) -> None:
    notebook = tmp_path / "blank.ipynb"
    notebook.write_text("", encoding="utf-8")

    result = runner.invoke(app, ["cell", "list", str(notebook)])

    assert result.exit_code == 0
    assert result.stdout == "| Index | ID | Type | Source Preview |\n| ----: | -- | ---- | -------------- |\n"


def test_insert_into_blank_file_creates_valid_notebook(tmp_path) -> None:
    notebook = tmp_path / "blank.ipynb"
    notebook.write_text("   \n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["cell", "insert", str(notebook), "start", "--type", "markdown"],
        input="# Hello\n",
    )

    assert result.exit_code == 0
    assert "operation: cell insert" in result.stdout

    saved = nbformat.read(notebook, as_version=4)
    assert len(saved.cells) == 1
    assert saved.cells[0]["cell_type"] == "markdown"
    assert saved.cells[0]["source"] == "# Hello\n"
