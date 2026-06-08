from __future__ import annotations


def render_cell_list(cells: list[dict]) -> str:
    rows = [
        "| Index | ID | Type | Source Preview |",
        "| ----: | -- | ---- | -------------- |",
    ]
    for index, cell in enumerate(cells, start=1):
        preview = source_preview(cell.get("source", ""))
        rows.append(
            f"| {index} | {cell.get('id', '')} | {cell.get('cell_type', '')} | {preview} |"
        )
    return "\n".join(rows)


def render_cell_source(cell: dict, index: int) -> str:
    lines = [
        f"<!-- cell id: {cell.get('id', '')} -->",
        f"<!-- cell index: {index} -->",
        f"<!-- cell type: {cell.get('cell_type', '')} -->",
        "",
    ]
    source = normalize_multiline(cell.get("source", ""))
    if cell.get("cell_type") == "code":
        lines.extend(["```python", source, "```"])
    else:
        lines.append(source)
    return "\n".join(lines).rstrip()


def source_preview(source: str) -> str:
    text = normalize_multiline(source).strip().replace("|", "\\|")
    if not text:
        return ""
    first_line = text.splitlines()[0]
    return first_line[:37] + "..." if len(first_line) > 40 else first_line


def normalize_multiline(value: str | list[str]) -> str:
    if isinstance(value, list):
        return "".join(value)
    return value
