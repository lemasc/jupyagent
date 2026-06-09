from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from jupyagent.cli import app

runner = CliRunner()


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


def test_output_read_normalizes_complex_html_table(tmp_path: Path) -> None:
    notebook = tmp_path / "pandas.ipynb"
    shutil.copy2(Path(__file__).parent / "fixtures" / "pandas.ipynb", notebook)

    result = runner.invoke(app, ["output", "read", str(notebook), "2"])

    assert result.exit_code == 0
    assert "```table" in result.stdout
    assert "- Region" in result.stdout
    assert "- Product" in result.stdout
    assert "- Metric > Sales" in result.stdout
    assert "- Metric > Profit" in result.stdout
    assert "- Region: East" in result.stdout
    assert "  Product: A" in result.stdout
    assert "  Metric > Sales: 10" in result.stdout
    assert "  Metric > Profit: 3" in result.stdout
    assert "  Product: B" in result.stdout
    assert "- Region: West" in result.stdout
    assert "<table" not in result.stdout
