#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]

for rel in ("port/src/optionsmenu.c", "port/src/androidcontrolsmenu.c"):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    bad = '(uintptr_t)"Restore Defaults\n",'
    # In the generated C, the Python string above represents an actual newline
    # between Defaults and the closing quote. Replace it with a C escape.
    good = '(uintptr_t)"Restore Defaults\\n",'
    count = s.count(bad)
    if count == 0:
        raise SystemExit(f"restore-default fix: no broken label found in {rel}")
    s = s.replace(bad, good)
    p.write_text(s, encoding="utf-8")
    print(f"restore-default fix: repaired {count} label(s) in {rel}")

p = root / "port/src/optionsmenu.c"
s = p.read_text(encoding="utf-8")
anchor = '#include "roomsheen.h"\n'
decl = '''#include "roomsheen.h"\n\n#ifdef ANDROID\nvoid androidControlsRestoreDefaults(void);\n#endif\n'''
if s.count(anchor) != 1:
    raise SystemExit(f"restore-default fix: Android declaration anchor count {s.count(anchor)}")
s = s.replace(anchor, decl, 1)
p.write_text(s, encoding="utf-8")
print("restore-default fix: declared Android reset helper")

p = root / "port/src/androidcontrolsmenu.c"
s = p.read_text(encoding="utf-8")
anchor = "static struct menuitem g_AndroidControllerSettingsMenuItems[];\n"
proto = anchor + "static MenuItemHandlerResult menuhandlerAndroidRestoreDefaults(s32 operation, struct menuitem *item, union handlerdata *data);\n"
if s.count(anchor) != 1:
    raise SystemExit(f"restore-default fix: Android handler declaration anchor count {s.count(anchor)}")
s = s.replace(anchor, proto, 1)
p.write_text(s, encoding="utf-8")
print("restore-default fix: declared Android Restore Defaults menu handler")

# This workflow step is already the final generated-source repair before the
# validation/build steps. Keep the general runtime pass separate from Restore
# Defaults itself, but invoke it here so later feature generators cannot
# overwrite the optimization.
import runpy
runpy.run_path(str(root / "android/optimize-core-runtime.py"), run_name="__main__")
