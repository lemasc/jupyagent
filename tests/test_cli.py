from __future__ import annotations

import base64
import json
import re
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


def test_cell_read_with_output_includes_saved_outputs(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "read", str(notebook_copy), "2", "--output"])
    assert result.exit_code == 0
    assert "```python" in result.stdout
    assert "## Outputs" in result.stdout
    assert "## Output 1" in result.stdout
    assert "```text\nhello\n```" in result.stdout


def test_cell_read_with_output_shows_missing_outputs(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "read", str(notebook_copy), "1", "--output"])
    assert result.exit_code == 0
    assert "# Title" in result.stdout
    assert "## Outputs" in result.stdout
    assert "_No saved outputs._" in result.stdout


def test_cell_path_returns_canonical_virtual_paths(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "path", str(notebook_copy), "all"])
    assert result.exit_code == 0
    assert "warning: detected 1 cell id issue" in result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "sample.ipynb/cells/0001__intro.source.md"
    assert lines[1] == "sample.ipynb/cells/0002__code-1.source.code"
    assert re.fullmatch(r"sample\.ipynb/cells/0003__[0-9a-f]{8}\.source\.md", lines[2])


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


def test_cell_patch_updates_multiple_cells_and_clears_code_outputs(notebook_copy: Path) -> None:
    patch = """--- sample.ipynb/cells/0001__intro.source.md
+++ sample.ipynb/cells/0001__intro.source.md
@@ -1,3 +1,3 @@
 # Title
 
-Intro text.
+Updated intro text.
--- sample.ipynb/cells/0002__code-1.source.code
+++ sample.ipynb/cells/0002__code-1.source.code
@@ -1 +1 @@
-print('hello')
+print('patched')
"""

    result = runner.invoke(app, ["cell", "patch", str(notebook_copy)], input=patch)
    assert result.exit_code == 0
    assert "operation: cell patch" in result.stdout
    assert "outputs_cleared: 1" in result.stdout
    assert "ids_repaired: 1" in result.stdout

    notebook = nbformat.read(notebook_copy, as_version=4)
    assert notebook.cells[0]["source"] == "# Title\n\nUpdated intro text.\n"
    assert notebook.cells[1]["source"] == "print('patched')\n"
    assert notebook.cells[1]["outputs"] == []
    assert notebook.cells[1]["execution_count"] is None


def test_cell_patch_rejects_unknown_virtual_path(notebook_copy: Path) -> None:
    patch = """--- sample.ipynb/cells/9999__missing.source.code
+++ sample.ipynb/cells/9999__missing.source.code
@@ -1 +1 @@
-print('hello')
+print('patched')
"""

    result = runner.invoke(app, ["cell", "patch", str(notebook_copy)], input=patch)
    assert result.exit_code == 1
    assert "did not match any cell" in result.stderr


def test_cell_patch_tolerates_incorrect_hunk_counts(notebook_copy: Path) -> None:
    patch = """--- sample.ipynb/cells/0001__intro.source.md
+++ sample.ipynb/cells/0001__intro.source.md
@@ -1,1 +1,1 @@
 # Title
 
-Intro text.
+Patched intro text.
"""

    result = runner.invoke(app, ["cell", "patch", str(notebook_copy)], input=patch)
    assert result.exit_code == 0
    assert "operation: cell patch" in result.stdout

    notebook = nbformat.read(notebook_copy, as_version=4)
    assert notebook.cells[0]["source"] == "# Title\n\nPatched intro text.\n"


def test_output_read_extracts_image_asset(notebook_copy: Path) -> None:
    notebook = json.loads(notebook_copy.read_text(encoding="utf-8"))
    notebook["cells"][1]["outputs"].append(
        {
            "output_type": "display_data",
            "data": {
                "text/plain": "<Figure size 1800x400 with 3 Axes>",
                "image/png": base64.b64encode(b"png-bytes").decode("ascii"),
            },
            "metadata": {},
        }
    )
    notebook_copy.write_text(json.dumps(notebook), encoding="utf-8")

    result = runner.invoke(app, ["output", "read", str(notebook_copy), "code-1"])
    assert result.exit_code == 0
    assert "![output image](.jupyagent/assets/sample/code-1/2.png)" in result.stdout
    assert (notebook_copy.parent / ".jupyagent" / "assets" / "sample" / "code-1" / "2.png").exists()


def test_exec_runs_notebook_in_place(exec_success_notebook: Path) -> None:
    result = runner.invoke(app, ["exec", str(exec_success_notebook)])

    assert result.exit_code == 0
    assert "operation: notebook exec" in result.stdout
    assert "modified: exec_success.ipynb" in result.stdout
    assert "executed_cells: 2" in result.stdout

    notebook = nbformat.read(exec_success_notebook, as_version=4)
    assert notebook.cells[0]["execution_count"] == 1
    assert notebook.cells[0]["outputs"][0]["text"] == "5\n"
    assert notebook.cells[1]["execution_count"] == 2
    assert notebook.cells[1]["outputs"][0]["data"]["text/plain"] == "10"


def test_exec_writes_to_output_path(exec_success_notebook: Path) -> None:
    output = exec_success_notebook.parent / "executed.ipynb"

    result = runner.invoke(
        app,
        ["exec", str(exec_success_notebook), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert f"modified: {output.name}" in result.stdout

    source_notebook = nbformat.read(exec_success_notebook, as_version=4)
    output_notebook = nbformat.read(output, as_version=4)
    assert source_notebook.cells[0]["execution_count"] is None
    assert output_notebook.cells[0]["execution_count"] == 1


def test_exec_reports_failure_and_writes_partial_outputs(exec_failure_notebook: Path) -> None:
    result = runner.invoke(app, ["exec", str(exec_failure_notebook)])

    assert result.exit_code == 1
    assert "operation: notebook exec" in result.stderr
    assert "status: failed" in result.stderr
    assert "index: 2" in result.stderr
    assert "id: boom" in result.stderr
    assert "ValueError: boom" in result.stderr

    notebook = nbformat.read(exec_failure_notebook, as_version=4)
    assert notebook.cells[0]["execution_count"] == 1
    assert notebook.cells[0]["outputs"][0]["text"] == "before\n"
    assert notebook.cells[1]["outputs"][0]["output_type"] == "error"


def test_missing_selector_exits_nonzero(notebook_copy: Path) -> None:
    result = runner.invoke(app, ["cell", "read", str(notebook_copy), "missing"])
    assert result.exit_code == 1
    assert "did not match any cell" in result.stderr
