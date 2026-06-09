from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag

from .errors import JupyagentError


def render_cell_outputs(notebook_path: Path, cell: dict, index: int) -> str:
    lines = [
        f"<!-- cell id: {cell.get('id', '')} -->",
        f"<!-- cell index: {index} -->",
        f"<!-- cell type: {cell.get('cell_type', '')} -->",
        "",
    ]
    outputs = cell.get("outputs", [])
    if not outputs:
        lines.append("_No saved outputs._")
        return "\n".join(lines)

    for output_index, output in enumerate(outputs, start=1):
        if output_index > 1:
            lines.append("")
        lines.append(f"## Output {output_index}")
        lines.append("")
        lines.extend(render_single_output(notebook_path, cell, output, output_index))
    return "\n".join(lines)


def render_single_output(notebook_path: Path, cell: dict, output: dict, output_index: int) -> list[str]:
    output_type = output.get("output_type")
    if output_type == "stream":
        return fenced("text", _join(output.get("text", "")))
    if output_type == "error":
        traceback = output.get("traceback") or [f"{output.get('ename', 'Error')}: {output.get('evalue', '')}"]
        return fenced("text", _join(traceback))

    data = output.get("data", {})
    if "text/markdown" in data:
        return [_join(data["text/markdown"])]
    if "text/html" in data:
        rendered_table = render_html_table(_join(data["text/html"]))
        if rendered_table is not None:
            return [rendered_table]
    if "text/plain" in data:
        return fenced("text", _join(data["text/plain"]))
    if "text/html" in data:
        html_text = BeautifulSoup(_join(data["text/html"]), "html.parser").get_text("\n")
        return fenced("text", html_text.strip())
    for mime_type, extension in (("image/png", "png"), ("image/jpeg", "jpg")):
        if mime_type in data:
            asset_path = write_image_asset(notebook_path, cell.get("id", "unknown"), output_index, extension, _join(data[mime_type]))
            return [f"![output image]({asset_path})"]
    supported = sorted(data.keys())
    label = supported[0] if supported else output_type or "unknown"
    return [f"_Unsupported output: {label}_"]


def write_image_asset(
    notebook_path: Path,
    cell_id: str,
    output_index: int,
    extension: str,
    encoded_data: str,
) -> str:
    asset_dir = notebook_path.parent / ".jupyagent" / "assets" / notebook_path.stem / cell_id
    try:
        asset_dir.mkdir(parents=True, exist_ok=True)
        asset_path = asset_dir / f"{output_index}.{extension}"
        asset_path.write_bytes(base64.b64decode(encoded_data))
    except Exception as exc:
        raise JupyagentError(f"error: failed to create assets for '{notebook_path.name}'") from exc
    return asset_path.relative_to(notebook_path.parent).as_posix()


def fenced(language: str, body: str) -> list[str]:
    return [f"```{language}", body.rstrip(), "```"]


@dataclass(frozen=True)
class TableCell:
    text: str
    is_header: bool


@dataclass
class PendingSpan:
    remaining_rows: int
    cell: TableCell


@dataclass(frozen=True)
class NormalizedTable:
    header_rows: list[list[TableCell]]
    body_rows: list[list[TableCell]]
    has_spans: bool


def render_html_table(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not isinstance(table, Tag):
        return None

    normalized = _normalize_html_table(table)
    if normalized is None:
        return None

    if _is_simple_table(normalized):
        return _render_simple_markdown_table(normalized)
    return _render_structured_table(normalized)


def _normalize_html_table(table: Tag) -> NormalizedTable | None:
    header_source_rows = _section_rows(table, "thead")
    body_source_rows = _section_rows(table, "tbody")
    if not body_source_rows:
        body_source_rows = _direct_body_rows(table)

    header_rows, header_has_spans = _expand_table_rows(header_source_rows)
    body_rows, body_has_spans = _expand_table_rows(body_source_rows)
    if not header_rows and not body_rows:
        return None

    width = max((len(row) for row in [*header_rows, *body_rows]), default=0)
    if width == 0:
        return None

    return NormalizedTable(
        header_rows=[_pad_cells(row, width) for row in header_rows],
        body_rows=[_pad_cells(row, width) for row in body_rows],
        has_spans=header_has_spans or body_has_spans,
    )


def _section_rows(table: Tag, section_name: str) -> list[Tag]:
    rows: list[Tag] = []
    for section in table.find_all(section_name, recursive=False):
        rows.extend(row for row in section.find_all("tr") if isinstance(row, Tag))
    return rows


def _direct_body_rows(table: Tag) -> list[Tag]:
    rows: list[Tag] = []
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        if any(isinstance(parent, Tag) and parent.name in {"thead", "tbody", "tfoot", "table"} for parent in row.parents):
            nearest_section = next((parent for parent in row.parents if isinstance(parent, Tag) and parent.name in {"thead", "tbody", "tfoot", "table"}), None)
            if nearest_section is table:
                rows.append(row)
    return rows


def _expand_table_rows(source_rows: list[Tag]) -> tuple[list[list[TableCell]], bool]:
    rows: list[list[TableCell]] = []
    pending: dict[int, PendingSpan] = {}
    has_spans = False

    for source_row in source_rows:
        row: list[TableCell] = []
        col = 0
        col = _fill_pending_cells(row, pending, col)

        for cell_tag in source_row.find_all(["th", "td"], recursive=False):
            col = _fill_pending_cells(row, pending, col)

            colspan = max(int(cell_tag.get("colspan", 1) or 1), 1)
            rowspan = max(int(cell_tag.get("rowspan", 1) or 1), 1)
            has_spans = has_spans or colspan > 1 or rowspan > 1
            cell = TableCell(text=_cell_text(cell_tag), is_header=cell_tag.name == "th")

            for offset in range(colspan):
                row.append(cell)
                if rowspan > 1:
                    pending[col + offset] = PendingSpan(remaining_rows=rowspan - 1, cell=cell)
            col += colspan

        _fill_pending_cells(row, pending, col)
        rows.append(row)

    return rows, has_spans


def _fill_pending_cells(row: list[TableCell], pending: dict[int, PendingSpan], col: int) -> int:
    while col in pending:
        span = pending[col]
        row.append(span.cell)
        if span.remaining_rows == 1:
            del pending[col]
        else:
            span.remaining_rows -= 1
        col += 1
    return col


def _pad_cells(row: list[TableCell], width: int) -> list[TableCell]:
    return row + [TableCell(text="", is_header=False)] * (width - len(row))


def _is_simple_table(table: NormalizedTable) -> bool:
    return not table.has_spans and len(table.header_rows) <= 1


def _render_simple_markdown_table(table: NormalizedTable) -> str | None:
    headers = [[cell.text for cell in row] for row in table.header_rows]
    rows = [[cell.text for cell in row] for row in table.body_rows]

    if not headers and rows and rows[0] and all(cell.is_header for cell in table.body_rows[0]):
        headers = [rows[0]]
        rows = rows[1:]

    flat_headers = headers[-1] if headers else []
    if not flat_headers and not rows:
        return None

    width = max(len(flat_headers), *(len(row) for row in rows), 0)
    if width == 0:
        return None

    normalized_headers = _pad_row(flat_headers, width) if flat_headers else [""] * width
    normalized_rows = [_pad_row(row, width) for row in rows]
    divider = ["---"] * width

    lines = [
        _markdown_table_row(normalized_headers),
        _markdown_table_row(divider),
        *(_markdown_table_row(row) for row in normalized_rows),
    ]
    return "\n".join(lines)


def _render_structured_table(table: NormalizedTable) -> str:
    width = max((len(row) for row in [*table.header_rows, *table.body_rows]), default=0)
    column_names = [_column_name(table.header_rows, index) for index in range(width)]
    row_header_count = _row_header_count(table.body_rows)
    column_names = [name or f"column_{index + 1}" for index, name in enumerate(column_names)]

    lines = ["columns:"]
    for name in column_names:
        lines.append(f"- {name}")

    lines.append("rows:")
    for row in table.body_rows:
        if not any(cell.text for cell in row):
            continue
        lines.append(f"- {column_names[0]}: {_table_scalar(row[0].text)}")
        for index, cell in enumerate(row[1:], start=1):
            lines.append(f"  {column_names[index]}: {_table_scalar(cell.text)}")

    if lines[-1] == "rows:":
        lines.append("- {}")

    return "\n".join(fenced("table", "\n".join(lines)))


def _column_name(header_rows: list[list[TableCell]], index: int) -> str:
    parts: list[str] = []
    for row in header_rows:
        if index >= len(row):
            continue
        text = row[index].text
        if not text or (parts and parts[-1] == text):
            continue
        parts.append(text)
    return " > ".join(parts)


def _row_header_count(body_rows: list[list[TableCell]]) -> int:
    if not body_rows:
        return 0

    width = max((len(row) for row in body_rows), default=0)
    count = 0
    for index in range(width):
        column_cells = [row[index] for row in body_rows if index < len(row)]
        if not column_cells:
            break
        if not all(cell.is_header for cell in column_cells):
            break
        if not any(any(not later.is_header and later.text for later in row[index + 1 :]) for row in body_rows):
            break
        count += 1
    return count


def _pad_row(row: list[str], width: int) -> list[str]:
    return row + [""] * (width - len(row))


def _markdown_table_row(row: list[str]) -> str:
    return "| " + " | ".join(_escape_markdown_cell(cell) for cell in row) + " |"


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")


def _cell_text(cell: Tag) -> str:
    text = cell.get_text(" ", strip=True)
    return " ".join(text.split())


def _table_scalar(value: str) -> str:
    return value if value else '""'


def _join(value: str | list[str]) -> str:
    if isinstance(value, list):
        return "".join(value)
    return value
