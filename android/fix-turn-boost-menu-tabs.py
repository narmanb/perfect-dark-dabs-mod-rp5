#!/usr/bin/env python3
from pathlib import Path

p = Path("port/src/optionsmenu.c")
s = p.read_text(encoding="utf-8")
start_marker = "static MenuItemHandlerResult menuhandlerTurnBoost(s32 op"
end_marker = "struct menudialogdef g_ExtendedStickMenuDialog = {"
start = s.find(start_marker)
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("turn boost generated menu block not found")
block = s[start:end]
count = block.count("\\t")
if count < 10:
    raise SystemExit(f"expected literal tab escapes in generated turn boost menu, found {count}")
block = block.replace("\\t", "\t")
s = s[:start] + block + s[end:]
p.write_text(s, encoding="utf-8")
print(f"fixed {count} literal tab escapes in turn boost menu")
