from __future__ import annotations

import base64
from pathlib import Path

from bs4 import BeautifulSoup

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


def _join(value: str | list[str]) -> str:
    if isinstance(value, list):
        return "".join(value)
    return value
