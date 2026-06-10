from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .errors import JupyagentError
from .operations import (
    delete_cells,
    execute_notebook,
    insert_cell,
    list_cell_paths,
    list_cells,
    move_cells,
    patch_cells,
    read_cells,
    read_outputs,
    read_source,
    replace_cell,
)

app = typer.Typer(no_args_is_help=True)
cell_app = typer.Typer(no_args_is_help=True)
output_app = typer.Typer(no_args_is_help=True)

app.add_typer(cell_app, name="cell")
app.add_typer(output_app, name="output")


@app.command("exec")
def exec_notebook(
    notebook: Path,
    timeout: Annotated[int | None, typer.Option("--timeout")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    _run(lambda: typer.echo(execute_notebook(notebook, timeout, output)))


@cell_app.command("list")
def cell_list(notebook: Path) -> None:
    _run(lambda: typer.echo(list_cells(notebook)))


@cell_app.command("read")
def cell_read(
    notebook: Path,
    selector: str,
    output: Annotated[bool, typer.Option("--output", help="Include saved cell outputs")] = False,
) -> None:
    _run(lambda: typer.echo(read_cells(notebook, selector, include_output=output)))


@cell_app.command("path")
def cell_path(notebook: Path, selector: str) -> None:
    _run(lambda: typer.echo(list_cell_paths(notebook, selector)))


@cell_app.command("insert")
def cell_insert(
    notebook: Path,
    position: str,
    cell_type: Annotated[str, typer.Option("--type")],
    file: Annotated[Path | None, typer.Option("--file")] = None,
) -> None:
    _run(lambda: typer.echo(insert_cell(notebook, position, cell_type, read_source(file))))


@cell_app.command("replace")
def cell_replace(
    notebook: Path,
    selector: str,
    cell_type: Annotated[str, typer.Option("--type")],
    file: Annotated[Path | None, typer.Option("--file")] = None,
    keep_outputs: bool = False,
) -> None:
    _run(
        lambda: typer.echo(
            replace_cell(notebook, selector, cell_type, read_source(file), keep_outputs)
        )
    )


@cell_app.command("delete")
def cell_delete(notebook: Path, selector: str) -> None:
    _run(lambda: typer.echo(delete_cells(notebook, selector)))


@cell_app.command("move")
def cell_move(notebook: Path, selector: str, position: str) -> None:
    _run(lambda: typer.echo(move_cells(notebook, selector, position)))


@cell_app.command("patch")
def cell_patch(
    notebook: Path,
    file: Annotated[Path | None, typer.Option("--file")] = None,
) -> None:
    _run(lambda: typer.echo(patch_cells(notebook, read_source(file))))


@output_app.command("read")
def output_read(notebook: Path, selector: str) -> None:
    _run(lambda: typer.echo(read_outputs(notebook, selector)))


def _run(action) -> None:
    try:
        action()
    except JupyagentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def main() -> None:
    app()


if __name__ == "__main__":
    main()
