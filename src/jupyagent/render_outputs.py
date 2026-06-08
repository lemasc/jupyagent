from __future__ import annotations

import base64
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
        markdown_table = render_html_table(_join(data["text/html"]))
        if markdown_table is not None:
            return [markdown_table]
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


def render_html_table(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not isinstance(table, Tag):
        return None

    headers = _extract_table_headers(table)
    rows = _extract_table_rows(table)
    if not headers and not rows:
        return None

    width = max(len(headers), *(len(row) for row in rows), 0)
    if width == 0:
        return None

    normalized_headers = _pad_row(headers, width) if headers else [""] * width
    normalized_rows = [_pad_row(row, width) for row in rows]
    divider = ["---"] * width

    lines = [
        _markdown_table_row(normalized_headers),
        _markdown_table_row(divider),
        *(_markdown_table_row(row) for row in normalized_rows),
    ]
    return "\n".join(lines)


def _extract_table_headers(table: Tag) -> list[str]:
    thead = table.find("thead")
    if isinstance(thead, Tag):
        for row in thead.find_all("tr"):
            header_cells = row.find_all(["th", "td"], recursive=False)
            if header_cells:
                return [_cell_text(cell) for cell in header_cells]

    first_row = table.find("tr")
    if isinstance(first_row, Tag):
        header_cells = first_row.find_all("th", recursive=False)
        if header_cells:
            return [_cell_text(cell) for cell in header_cells]
    return []


def _extract_table_rows(table: Tag) -> list[list[str]]:
    rows: list[list[str]] = []
    body_sections = table.find_all("tbody") or [table]
    for section in body_sections:
        if not isinstance(section, Tag):
            continue
        for row in section.find_all("tr", recursive=section.name == "table"):
            cells = row.find_all(["th", "td"], recursive=False)
            if cells:
                rows.append([_cell_text(cell) for cell in cells])
    return rows


def _pad_row(row: list[str], width: int) -> list[str]:
    return row + [""] * (width - len(row))


def _markdown_table_row(row: list[str]) -> str:
    return "| " + " | ".join(_escape_markdown_cell(cell) for cell in row) + " |"


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")


def _cell_text(cell: Tag) -> str:
    text = cell.get_text(" ", strip=True)
    return " ".join(text.split())


def _join(value: str | list[str]) -> str:
    if isinstance(value, list):
        return "".join(value)
    return value
