#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path, old, new, expected=1):
    p = ROOT / path
    text = p.read_text()
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"postfx menu fix: expected {expected} occurrence(s) of {old!r} in {path}, found {count}")
    p.write_text(text.replace(old, new))
    print(f"postfx menu fix: patched {path}")


# menuitem layout is type,param,flags,param2,param3,handler.  The Post FX
# macros put the visible label in param2 and the setting pointer in param3.
# The first implementation accidentally dereferenced param2, treating the
# label string as an s32 setting; menu initialisation then receives a garbage
# selected index and can crash before the first page is shown.
replace_exact(
    "port/src/optionsmenu.c",
    "s32 *value = (s32 *)item->param2;",
    "s32 *value = (s32 *)item->param3;",
    expected=2,
)

# Dab's Mod Options already used all five sibling slots.  Post FX is a sixth
# page, so grow the sibling array and make the loader follow the array size
# rather than a stale magic number.  Dialog/row/block pools are already larger
# than this page set needs.
replace_exact(
    "src/include/types.h",
    "struct menudialog *siblings[5];",
    "struct menudialog *siblings[8];",
)
replace_exact(
    "src/game/menu.c",
    "while (sibling && layer->numsiblings < 5) {",
    "while (sibling && layer->numsiblings < ARRAYCOUNT(layer->siblings)) {",
)
