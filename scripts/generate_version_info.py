from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "dport_version.py"
OUTPUT_FILE = ROOT / "version_info.generated.txt"

raw = VERSION_FILE.read_text(encoding="utf-8")
match = re.search(r'DPORT_VERSION\s*=\s*["\']([^"\']+)["\']', raw)
if not match:
    raise SystemExit("DPORT_VERSION not found in src/dport_version.py")

version = match.group(1).strip()
parts = version.split(".")
if len(parts) != 3 or not all(part.isdigit() for part in parts):
    raise SystemExit(f"Invalid DPort version: {version}")
major, minor, patch = (int(part) for part in parts)

content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major},{minor},{patch},0),
    prodvers=({major},{minor},{patch},0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0,0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040404B0',
        [
          StringStruct('CompanyName', 'Dicky'),
          StringStruct('FileDescription', 'DPort'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'DPort-{version}'),
          StringStruct('LegalCopyright', 'Dicky'),
          StringStruct('OriginalFilename', 'DPort-{version}.exe'),
          StringStruct('ProductName', 'DPort'),
          StringStruct('ProductVersion', '{version}'),
          StringStruct('Comments', 'Dicky'),
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [0x0404, 1200])])
  ]
)
"""
OUTPUT_FILE.write_text(content, encoding="utf-8")
print(f"Generated {OUTPUT_FILE.name} for DPort {version}")
