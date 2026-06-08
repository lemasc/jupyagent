# jupyagent

`jupyagent` is an agent-first CLI for inspecting and editing Jupyter notebooks without working directly with raw `.ipynb` JSON.

This MVP focuses on notebook file management only:

- list cells
- read cell source
- read saved outputs
- insert, replace, delete, and move cells

It does not execute notebooks or manage kernels.

## Why It Exists

Notebook JSON is noisy for both humans and coding agents. `jupyagent` exposes common notebook operations as small CLI commands with readable Markdown output and safe in-place mutations.

## Install

Clone this repository, activate your virtual environment, and install this project directly.

```
pip install -e .
```

## Development Install

This workspace is configured with `uv`.

```bash
uv sync --dev
```

Run the CLI with:

```bash
source .venv/bin/activate
jupyagent --help
```

## Agent Guidance

Use `jupyagent` when you need to inspect or modify notebook structure without editing `.ipynb` JSON directly.

Good uses:

- inspect notebook structure before making changes
- read one or more cells as Markdown or fenced code
- read saved outputs, including extracted images
- insert or replace cells from stdin or a file
- reorder cells safely

Recommended workflow for agents:

1. Start with `jupyagent cell list <notebook>`.
2. Read specific cells with `jupyagent cell read <notebook> <selector>`.
3. Read saved outputs with `jupyagent output read <notebook> <selector>` when needed.
4. Apply structural edits with `cell insert`, `cell replace`, `cell delete`, or `cell move`.
5. Re-run `cell list` or `cell read` to verify the result.

Notes:

- Read-only commands do not rewrite notebooks.
- Mutating commands repair missing or duplicate cell IDs before writing.
- `output read` may create files under `.jupyagent/assets/` for extracted images.
- Replacing a code cell clears saved outputs by default.

## Command Overview

```bash
jupyagent cell list <notebook>
jupyagent cell read <notebook> <selector>
jupyagent cell insert <notebook> <position> --type code|markdown|raw [--file <path>]
jupyagent cell replace <notebook> <selector> --type code|markdown|raw [--file <path>] [--keep-outputs]
jupyagent cell delete <notebook> <selector>
jupyagent cell move <notebook> <selector> <position>

jupyagent output read <notebook> <selector>
```

## Selectors

Supported selector forms:

```text
<cell-id>    Cell ID, such as abc123
<index>      One-based cell index, such as 4
<start>:<end> Inclusive one-based cell index range, such as 2:6
all          All cells
```

Resolution rules:

- If a selector matches an existing cell ID, it is treated as a cell ID.
- Numeric selectors are treated as one-based indexes.
- Range selectors are inclusive.
- Some commands require the selector to resolve to exactly one cell.

Examples:

```bash
jupyagent cell read analysis.ipynb abc123
jupyagent cell read analysis.ipynb 4
jupyagent cell read analysis.ipynb 2:6
jupyagent output read analysis.ipynb all
```

## Positions

Supported position forms:

```text
start
end
before:<selector>
after:<selector>
```

Examples:

```bash
jupyagent cell insert analysis.ipynb start --type markdown
jupyagent cell insert analysis.ipynb after:abc123 --type code < transform.py
jupyagent cell move analysis.ipynb 3:5 end
```

## Usage Examples

List cells:

```bash
jupyagent cell list analysis.ipynb
```

Read a code cell:

```bash
jupyagent cell read analysis.ipynb 2
```

Insert a markdown cell from a file:

```bash
jupyagent cell insert analysis.ipynb end --type markdown --file notes.md
```

Insert a code cell from stdin:

```bash
jupyagent cell insert analysis.ipynb after:prep --type code < transform.py
```

Replace a cell and clear old outputs:

```bash
jupyagent cell replace analysis.ipynb 2 --type code < transform.py
```

Replace a code cell but keep saved outputs:

```bash
jupyagent cell replace analysis.ipynb abc123 --type code --keep-outputs < transform.py
```

Delete a range of cells:

```bash
jupyagent cell delete analysis.ipynb 3:5
```

Move cells to the end:

```bash
jupyagent cell move analysis.ipynb 3:5 end
```

Read saved outputs:

```bash
jupyagent output read analysis.ipynb 2
```

## Output Behavior

`output read` renders saved outputs as Markdown where possible.

Current MVP support:

- `text/markdown`
- `text/plain`
- `text/html` converted to readable text
- `image/png`
- `image/jpeg`

Image outputs are extracted automatically to:

```text
.jupyagent/assets/<notebook-stem>/<cell-id>/
```

The emitted Markdown uses relative asset paths.

## Write Semantics

Mutating commands:

- read the existing notebook
- apply the requested operation
- repair missing or duplicate cell IDs
- preserve notebook metadata where possible
- write to a temporary file in the same directory
- atomically replace the original notebook

## Errors

Commands return non-zero exit codes on failure.

Example:

```text
error: selector 'abc123' did not match any cell in analysis.ipynb
```

## Status

This is an MVP implementation.

Implemented now:

- `cell list`
- `cell read`
- `cell insert`
- `cell replace`
- `cell delete`
- `cell move`
- `output read`

Not yet implemented:

- notebook execution
- kernel management
- `cell patch`
