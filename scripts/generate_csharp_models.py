"""Generate SDK domain DTOs from the exported C# wire contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic.alias_generators import to_snake


def python_type(shape: dict[str, Any]) -> str:
    """Map an exported CLR type to an SDK business model annotation."""
    kind = shape["kind"]
    if kind == "model":
        return {
            "Vector3d": "Vector3", "Vector4d": "Vector4",
            "Vector6d": "Vector6",
        }.get(shape["name"], shape["name"])
    if kind == "list":
        return f"list[{python_type(shape['item'])}]"
    if kind == "dict":
        # JSON object keys are strings, including Dictionary<long, T>.
        return f"dict[str, {python_type(shape['item'])}]"
    return {"json": "JsonValue", "bytes": "Base64Bytes"}.get(kind, kind)


def field_line(prop: dict[str, Any]) -> str:
    """Preserve the exact JSON alias and C# initializer for one property."""
    name = {"VVLHRV": "vvlh_rv"}.get(prop["name"], to_snake(prop["name"]))
    shape = prop["type"]
    kind = shape["kind"]
    annotation = python_type(shape)
    if prop["nullable"]:
        annotation += " | None"
    value = prop["default"]
    if value is None:
        default = "default=None"
    elif kind in {"dict", "list"}:
        default = f"default_factory={kind}"
    elif kind == "model":
        if shape["name"].startswith("Vector"):
            default = f"default_factory=lambda: {annotation}({value!r})"
        else:
            default = f"default_factory=lambda: {annotation}()"
    elif kind == "datetime":
        default = (
            "default_factory=lambda: datetime.fromisoformat(\n"
            f"            {value!r}\n        )"
        )
    else:
        default = f"default={value!r}"
    read_only = (
        '        json_schema_extra={"readOnly": True},\n'
        if prop["readOnly"] else ""
    )
    return (
        f"    {name}: {annotation} = Field(\n"
        f"        {default},\n"
        f"        alias={prop['alias']!r},\n"
        f"{read_only}"
        "    )"
    )


def main() -> None:
    """Generate a deterministic Python module; fail on unsupported types."""
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract", type=Path,
        default=root / "tests/fixtures/csharp_condition_contract.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=root / "src/algo_dto/csharp_models.py",
    )
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8-sig"))
    version = contract["assembly"].split("Version=", 1)[1].split(",", 1)[0]
    version = version.removesuffix(".0")
    chunks = [
        f'"""Generated C# ProjectDTO/SimData wire models (LJ.DTO {version}).',
        "",
        "Regenerate using scripts/generate_csharp_models.py.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from datetime import datetime",
        "",
        "from pydantic import Base64Bytes, ConfigDict, Field, JsonValue",
        "",
        "from algo_dto.base import CamelBaseModel, Vector3, Vector4, Vector6",
        "",
        "",
        "class CSharpDtoModel(CamelBaseModel):",
        '    """Typed properties with forward-compatible JSON extras."""',
        "",
        '    model_config = ConfigDict(extra="allow")',
    ]
    for name, model in contract["models"].items():
        chunks.extend([
            "", "", f"class {name}(CSharpDtoModel):",
            f'    """Serialized {model["source"]} properties."""', "",
        ])
        chunks.extend(field_line(prop) for prop in model["properties"])
    chunks.extend(["", "", "__all__ = ["])
    chunks.extend(f'    "{name}",' for name in contract["models"])
    chunks.extend([
        "]", "", "# Resolve recursive equipment and cross-model references.",
        "for _model_name in __all__:",
        "    globals()[_model_name].model_rebuild()", "",
    ])
    args.output.write_text("\n".join(chunks), encoding="utf-8")
    print(f"Generated {len(contract['models'])} C# models: {args.output}")


if __name__ == "__main__":
    main()
