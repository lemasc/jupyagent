# jupyagent

`jupyagent` is an agent-first CLI for inspecting and editing Jupyter notebooks without working directly with raw `.ipynb` JSON.

This MVP focuses on notebook file management and stateless full-notebook execution:

- list cells
- read cell source
- read saved outputs
- insert, replace, delete, and move cells
- patch one or more cell sources with unified diffs
- execute a notebook from top to bottom

It does not provide interactive or persistent kernel management.

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
5. Use `cell path` and `cell patch` for source-level edits across multiple cells.
6. Run `jupyagent exec <notebook>` when you need fresh outputs.
7. Re-run `cell list`, `cell read`, or `output read` to verify the result.

Notes:

- Read-only commands do not rewrite notebooks.
- Mutating commands repair missing or duplicate cell IDs before writing.
- `output read` may create files under `.jupyagent/assets/` for extracted images.
- Replacing or patching a code cell clears saved outputs and execution count.

## Command Overview

```bash
jupyagent cell list <notebook>
jupyagent cell read <notebook> <selector> [--output]
jupyagent cell path <notebook> <selector>
jupyagent cell insert <notebook> <position> --type code|markdown|raw [--file <path>]
jupyagent cell replace <notebook> <selector> --type code|markdown|raw [--file <path>] [--keep-outputs]
jupyagent cell delete <notebook> <selector>
jupyagent cell move <notebook> <selector> <position>
jupyagent cell patch <notebook> [--file <path>]

jupyagent output read <notebook> <selector>
jupyagent exec <notebook> [--timeout <seconds>] [--output <path>]
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
jupyagent cell read analysis.ipynb 2 --output
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

## Virtual Paths

`cell patch` targets canonical virtual cell source paths.

Always get these paths from `jupyagent cell path <notebook> <selector>` instead of constructing them by hand.

Format:

```text
<notebook-name>.ipynb/cells/<index-padded>__<cell-id>.source.<ext>
```

Examples:

```text
analysis.ipynb/cells/0001__intro.source.md
analysis.ipynb/cells/0002__prep.source.code
analysis.ipynb/cells/0003__notes.source.raw
```

Rules:

- Paths are canonical. `cell patch` matches these exact paths.
- Paths are generated after in-memory cell ID repair, so duplicate or missing notebook IDs may appear with repaired IDs.
- `cell path` does not rewrite the notebook file.
- `cell patch` only edits cell source content. It does not create, delete, move, or patch outputs or metadata.
- Extensions map to cell types: `code -> .code`, `markdown -> .md`, `raw -> .raw`.

## Usage Examples

List cells:

```bash
jupyagent cell list analysis.ipynb
```

Read a code cell:

```bash
jupyagent cell read analysis.ipynb 2
```

Show canonical virtual paths:

```bash
jupyagent cell path analysis.ipynb 2:3
```

Read a code cell with saved outputs:

```bash
jupyagent cell read analysis.ipynb 2 --output
```

Insert a markdown cell from a file:

```bash
jupyagent cell insert analysis.ipynb end --type markdown --file notes.md
```

Insert a code cell from stdin:

```bash
jupyagent cell insert analysis.ipynb after:prep --type code < transform.py
```

Insert a code cell from a multiline heredoc:

```bash
cat <<'EOF' | jupyagent cell insert analysis.ipynb end --type code
import pandas as pd

df = pd.read_csv("data.csv")
df.head()
EOF
```

Replace a cell and clear old outputs:

```bash
jupyagent cell replace analysis.ipynb 2 --type code < transform.py
```

Replace a cell from a multiline heredoc:

```bash
cat <<'EOF' | jupyagent cell replace analysis.ipynb 2 --type markdown
## Summary

- Loaded the latest dataset
- Recomputed the aggregate metrics
EOF
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

Patch two cells at once:

```diff
--- analysis.ipynb/cells/0002__prep.source.code
+++ analysis.ipynb/cells/0002__prep.source.code
@@ -1 +1 @@
-print("old")
+print("new")
--- analysis.ipynb/cells/0004__summary.source.md
+++ analysis.ipynb/cells/0004__summary.source.md
@@ -1 +1 @@
-Old summary
+New summary
```

```bash
jupyagent cell patch analysis.ipynb < changes.diff
```

Read saved outputs:

```bash
jupyagent output read analysis.ipynb 2
```

Execute a notebook in place:

```bash
jupyagent exec analysis.ipynb
```

Execute a notebook and write the result elsewhere:

```bash
jupyagent exec analysis.ipynb --output analysis.executed.ipynb
```

## Execution Behavior

`exec` performs a stateless batch execution of the full notebook using the notebook's configured kernel.

- execution always starts from the first cell
- outputs are saved back into the notebook file by default
- `--output` writes the executed notebook to a new path instead of modifying the source file
- failures return a non-zero exit code and report the failing cell
- partial outputs up to the failing cell are preserved in the written notebook
- this is intended for exploratory and batch workflows, not long-running interactive sessions

## Output Behavior

`output read` renders saved outputs as Markdown where possible.

Current MVP support:

- `text/markdown`
- `text/plain`
- simple `text/html` tables converted to Markdown tables
- complex `text/html` tables normalized into row-oriented fenced `table` blocks
- other `text/html` output converted to readable text
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
- `cell path`
- `cell patch`
- `output read`
- `exec`

Not yet implemented:

- kernel management
