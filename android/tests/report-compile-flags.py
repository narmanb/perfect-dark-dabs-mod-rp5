#!/usr/bin/env python3
"""Summarize the effective optimization flags from CMake compile_commands.json.

This is deliberately diagnostic-only. It does not infer optimization from the
Gradle variant name or CMakeLists.txt; it reports the actual clang command line
recorded for each translation unit, where the last -O flag wins.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from collections import Counter, defaultdict
from pathlib import Path

OPT_RE = re.compile(r"^-O(?:0|1|2|3|g|s|z|fast)?$")
KEY_FILES = (
    "port/fast3d/gfx_opengl.cpp",
    "port/fast3d/gfx_pc.cpp",
    "port/fast3d/gfx_texscale.cpp",
    "port/src/xblamesh.c",
    "port/src/audio.c",
    "src/game/menu.c",
    "src/game/menugfx.c",
    "src/game/menutick.c",
    "src/game/lv.c",
    "src/game/chr.c",
    "src/game/prop.c",
    "src/lib/collision.c",
    "src/lib/model.c",
)
INTERESTING_FLAGS = {
    "-g",
    "-g0",
    "-g1",
    "-g2",
    "-g3",
    "-DNDEBUG",
    "-fno-inline-functions",
    "-finline-functions",
    "-ffast-math",
    "-fno-strict-aliasing",
    "-fwrapv",
}


def argv_for(entry: dict) -> list[str]:
    if isinstance(entry.get("arguments"), list):
        return [str(x) for x in entry["arguments"]]
    command = entry.get("command", "")
    return shlex.split(command)


def source_path(entry: dict) -> str:
    src = Path(entry.get("file", ""))
    directory = Path(entry.get("directory", "."))
    if not src.is_absolute():
        src = directory / src
    try:
        return src.resolve().as_posix()
    except OSError:
        return src.as_posix()


def short_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    for marker in ("/port/", "/src/", "/android/"):
        pos = normalized.rfind(marker)
        if pos >= 0:
            return normalized[pos + 1 :]
    return normalized


def category(path: str) -> str:
    p = short_path(path)
    if p.startswith("port/fast3d/"):
        return "port/fast3d"
    if p.startswith("port/"):
        return "port/other"
    if p.startswith("src/game/"):
        return "src/game"
    if p.startswith("src/lib/"):
        return "src/lib"
    if p.startswith("src/"):
        return "src/other"
    return "other"


def find_cache(ccdb: Path) -> Path | None:
    here = ccdb.parent
    for base in (here, *here.parents[:4]):
        candidate = base / "CMakeCache.txt"
        if candidate.is_file():
            return candidate
    return None


def cache_values(cache: Path | None) -> dict[str, str]:
    wanted = {
        "CMAKE_BUILD_TYPE",
        "CMAKE_C_FLAGS",
        "CMAKE_C_FLAGS_DEBUG",
        "CMAKE_C_FLAGS_RELEASE",
        "CMAKE_CXX_FLAGS",
        "CMAKE_CXX_FLAGS_DEBUG",
        "CMAKE_CXX_FLAGS_RELEASE",
        "PD_DECOMP_O2",
        "PD_HOT_O2",
    }
    result: dict[str, str] = {}
    if cache is None:
        return result
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("#") or line.startswith("//") or "=" not in line:
            continue
        lhs, value = line.split("=", 1)
        name = lhs.split(":", 1)[0]
        if name in wanted:
            result[name] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("compile_commands", type=Path)
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--json", dest="json_out", type=Path, required=True)
    args = parser.parse_args()

    db = json.loads(args.compile_commands.read_text(encoding="utf-8"))
    records = []
    for entry in db:
        argv = argv_for(entry)
        opts = [token for token in argv if OPT_RE.fullmatch(token)]
        path = source_path(entry)
        record = {
            "file": short_path(path),
            "absolute_file": path,
            "category": category(path),
            "optimization_flags_in_order": opts,
            "effective_optimization": opts[-1] if opts else "<none>",
            "interesting_flags": [
                token
                for token in argv
                if token in INTERESTING_FLAGS or token.startswith("-g") and re.fullmatch(r"-g[0-3]?", token)
            ],
        }
        records.append(record)

    counts = Counter(r["effective_optimization"] for r in records)
    grouped: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        grouped[r["category"]][r["effective_optimization"]] += 1

    cache = find_cache(args.compile_commands)
    cache_info = cache_values(cache)

    by_file = {r["file"]: r for r in records}
    key_records = {name: by_file.get(name) for name in KEY_FILES}

    payload = {
        "compile_commands": str(args.compile_commands),
        "cmake_cache": str(cache) if cache else None,
        "cmake": cache_info,
        "translation_units": len(records),
        "effective_optimization_counts": dict(sorted(counts.items())),
        "by_category": {
            name: dict(sorted(values.items())) for name, values in sorted(grouped.items())
        },
        "key_files": key_records,
        "all_files": records,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("Perfect Dark Android native compile flag audit")
    lines.append("================================================")
    lines.append(f"compile_commands: {args.compile_commands}")
    lines.append(f"CMakeCache: {cache if cache else '<not found>'}")
    if cache_info:
        for name, value in cache_info.items():
            lines.append(f"{name}={value}")
    lines.append("")
    lines.append(f"Translation units: {len(records)}")
    lines.append("Effective optimization (last -O flag on each actual clang command):")
    for flag, count in sorted(counts.items()):
        lines.append(f"  {flag:8s} {count}")

    lines.append("")
    lines.append("By source area:")
    for name, values in sorted(grouped.items()):
        rendered = ", ".join(f"{flag}={count}" for flag, count in sorted(values.items()))
        lines.append(f"  {name:14s} {rendered}")

    lines.append("")
    lines.append("Key translation units:")
    for name in KEY_FILES:
        record = key_records[name]
        if record is None:
            lines.append(f"  {name}: NOT FOUND")
            continue
        ordered = " ".join(record["optimization_flags_in_order"]) or "<none>"
        extras = " ".join(record["interesting_flags"]) or "<none>"
        lines.append(
            f"  {name}: effective={record['effective_optimization']} "
            f"ordered_O_flags=[{ordered}] extras=[{extras}]"
        )

    lines.append("")
    lines.append("Files without an explicit -O flag in the recorded command:")
    no_opt = [r["file"] for r in records if r["effective_optimization"] == "<none>"]
    if no_opt:
        lines.extend(f"  {name}" for name in no_opt)
    else:
        lines.append("  <none>")

    text = "\n".join(lines) + "\n"
    args.text.parent.mkdir(parents=True, exist_ok=True)
    args.text.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
