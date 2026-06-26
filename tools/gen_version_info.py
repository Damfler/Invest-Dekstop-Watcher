"""
Генерирует version_info.txt для PyInstaller из version.py.
Единый источник версии — только version.py.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from version import APP_VERSION, APP_NAME


def _parse_version(v: str) -> tuple[int, int, int, int]:
    parts: list[int] = []
    for p in v.strip().lstrip("vV").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def main() -> None:
    ver = _parse_version(APP_VERSION)
    ver_str = APP_VERSION
    out = os.path.join(BASE, "version_info.txt")
    content = f"""# UTF-8
# Auto-generated from version.py — do not edit manually
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={ver},
    prodvers={ver},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Damfler'),
        StringStruct('FileDescription', '{APP_NAME}'),
        StringStruct('FileVersion', '{ver_str}'),
        StringStruct('InternalName', 'Stack'),
        StringStruct('LegalCopyright', 'MIT License'),
        StringStruct('OriginalFilename', 'Stack.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{ver_str}')])
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated {out} for {APP_NAME} v{ver_str}")


if __name__ == "__main__":
    main()
