from __future__ import annotations

import ast
import compileall
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
INJECTED_IDS = (
    "dport-final-ui-polish-v8",
    "dport-final-favorites-render-v8",
    "dport-map-status-overlay-script",
    "dport-header-brand-version-final",
    "dport-exact-copy-button-appearance",
    "dport-copy-button-style-sync",
    "dport-usb-manual-refresh-status",
    "dport-usb-manual-refresh-only",
    "dport-unified-status-final",
    "dport-unified-status-final-script",
    "dport-location-gpx-interaction-final",
    "dport-location-gpx-interaction-final-script",
    "dport-definitive-location-gpx-fix",
    "dport-definitive-location-gpx-fix-script",
)
FORBIDDEN = ("moenv_api_key", "MOENV", "public_toilet", "PUBLIC_TOILET", "公共廁所")
EXCLUDED_AUDIT_PATHS = {Path(__file__).resolve()}


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def extract_script_blocks(html: str) -> list[str]:
    blocks: list[str] = []
    pos = 0
    while True:
        start = html.find("<script", pos)
        if start < 0:
            break
        gt = html.find(">", start)
        if gt < 0:
            raise RuntimeError("Unclosed <script> tag.")
        end = html.find("</script>", gt + 1)
        if end < 0:
            raise RuntimeError("Missing </script> tag.")
        code = html[gt + 1:end]
        if code.strip():
            blocks.append(code)
        pos = end + len("</script>")
    return blocks


def get_stable_release_tags(limit: int = 2) -> list[str]:
    url = "https://api.github.com/repos/DickyR15/DPort/releases?per_page=100"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "DPort-Full-Audit"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        releases = json.load(response)

    stable = [
        str(r["tag_name"])
        for r in releases
        if not r.get("draft")
        and not r.get("prerelease")
        and re.fullmatch(r"v\d+\.\d+\.\d+", str(r.get("tag_name", "")))
    ]
    stable.sort(key=lambda tag: tuple(int(x) for x in tag[1:].split(".")), reverse=True)
    return stable[:limit]


def audit_tag(ref: str) -> list[str]:
    failures: list[str] = []
    print("=" * 70)
    print("AUDIT", ref)

    run("git", "fetch", "origin", f"refs/tags/{ref}:refs/tags/{ref}")
    run("git", "switch", "--detach", "--force", ref)

    version_line = next(
        (line.strip() for line in read_text("src/dport_version.py").splitlines()
         if line.strip().startswith("DPORT_VERSION=")),
        None,
    )
    if not version_line:
        failures.append("DPORT_VERSION is missing.")
    else:
        version = version_line.split("=", 1)[1].strip().strip("\"'")
        if f"v{version}" != ref:
            failures.append(f"Source version mismatch: {version} != {ref}")
    version = ref[1:]

    required = (
        "src/main.py",
        "src/dport_version.py",
        "src/dport_release_updater.py",
        "src/dport_updater_helper.py",
        "src/templates/map.html",
        "requirements-build.txt",
        "build_final_live.bat",
    )
    for item in required:
        if not (ROOT / item).exists():
            failures.append(f"Missing required file: {item}")

    if not compileall.compile_dir(str(ROOT / "src"), quiet=1):
        failures.append("compileall failed for src/")
    if not compileall.compile_dir(str(ROOT / "scripts"), quiet=1):
        failures.append("compileall failed for scripts/")

    req_lines = read_text("requirements-build.txt").splitlines()
    pm3 = next((x.split("==", 1)[1].strip() for x in req_lines if x.strip().startswith("pymobiledevice3==")), None)
    if not pm3:
        failures.append("pymobiledevice3 pin missing.")
    else:
        print("pymobiledevice3:", pm3)

    html = read_text("src/templates/map.html")
    try:
        blocks = extract_script_blocks(html)
        node = shutil.which("node")
        if not node:
            failures.append("Node.js is not installed.")
        else:
            with tempfile.TemporaryDirectory() as td:
                for i, code in enumerate(blocks):
                    js = Path(td) / f"block-{i}.js"
                    js.write_text(code, encoding="utf-8")
                    result = subprocess.run([node, "--check", str(js)], cwd=ROOT)
                    if result.returncode != 0:
                        failures.append(f"JavaScript syntax error in inline script #{i}.")
    except Exception as exc:
        failures.append(f"JavaScript extraction failed: {exc}")

    for block_id in INJECTED_IDS:
        count = html.count(f'id="{block_id}"') + html.count(f"id='{block_id}'")
        if count != 1:
            failures.append(f"Injected block ID {block_id!r} appears {count} times.")

    try:
        tree = ast.parse(read_text("src/main.py"))
        routes: Counter[str] = Counter()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name)
                    and dec.func.value.id == "app"
                    and dec.func.attr == "route"
                    and dec.args
                    and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)
                ):
                    routes[dec.args[0].value] += 1
        for route, count in routes.items():
            if count > 1:
                failures.append(f"Duplicate Flask route {route!r} appears {count} times.")
    except Exception as exc:
        failures.append(f"AST route audit failed: {exc}")

    # Historical release tags are audited for release integrity; current build tooling is checked on the live ref.

    # version_info.txt is a legacy/static metadata file and is not the source
    # used by current builds. Release builds generate version_info.generated.txt
    # from src/dport_version.py, so audit the generated metadata instead.
    run(sys.executable, "scripts/generate_version_info.py")
    generated_version_info = ROOT / "version_info.generated.txt"
    if not generated_version_info.exists():
        failures.append("Generated version_info.generated.txt is missing.")
    else:
        generated = generated_version_info.read_text(
            encoding="utf-8", errors="replace"
        )
        if not re.search(
            r"FileVersion'\s*,\s*'" + re.escape(version) + r"'",
            generated,
        ):
            failures.append("Generated version_info.txt FileVersion mismatch.")
        if not re.search(
            r"ProductVersion'\s*,\s*'" + re.escape(version) + r"'",
            generated,
        ):
            failures.append("Generated version_info.txt ProductVersion mismatch.")

    updater = read_text("src/dport_release_updater.py")
    for needle in ("RELEASES_API", "_get_latest_stable_release", "_is_newer"):
        if needle not in updater:
            failures.append(f"Updater missing {needle}.")

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".github" in path.parts:
            continue
        if path.resolve() in EXCLUDED_AUDIT_PATHS:
            continue
        if path.suffix.lower() not in {".py", ".bat", ".txt", ".md", ".yml", ".yaml", ".html", ".js", ".json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for token in FORBIDDEN:
            if token in text:
                failures.append(f"Legacy forbidden text {token!r} remains in {path.relative_to(ROOT)}.")

    print(ref, "FAIL" if failures else "PASS")
    for item in failures:
        print(" -", item)
    return failures


def audit_current_source() -> list[str]:
    """Validate version-agnostic rules that apply to the current source tree."""
    failures: list[str] = []

    bat = read_text("build_final_live.bat")
    if "DPort-6.9.0.ico" in bat:
        failures.append("build_final_live.bat hardcodes a versioned DPort icon.")
    if "DPortUpdater.exe" in bat:
        failures.append("build_final_live.bat still contains legacy DPortUpdater.exe naming.")
    if "DPort-Updater.exe" not in bat:
        failures.append("build_final_live.bat does not use DPort-Updater.exe.")
    if "DPORT_ICON" not in bat or 'DPort-*.ico' not in bat:
        failures.append("build_final_live.bat does not resolve the DPort icon dynamically.")

    release_workflow = read_text(".github/workflows/dport-windows-build-release.yml")
    if "DPort-6.9.0.ico" in release_workflow:
        failures.append("Release workflow hardcodes DPort-6.9.0.ico.")
    if "DPortUpdater.exe" in release_workflow:
        failures.append("Release workflow contains legacy DPortUpdater.exe naming.")
    if "DPort-Updater.exe" not in release_workflow:
        failures.append("Release workflow does not use DPort-Updater.exe.")
    if "steps.version.outputs.python_version" not in release_workflow:
        failures.append("Release workflow does not use dynamic Python build version metadata.")
    if "steps.version.outputs.pm3_version" not in release_workflow:
        failures.append("Release workflow does not use dynamic pymobiledevice3 version metadata.")

    pm3_workflow = read_text(".github/workflows/pymobiledevice3-auto-update.yml")
    if "DPort-6.9.0.ico" in pm3_workflow:
        failures.append("pymobiledevice3 Auto Update workflow hardcodes DPort-6.9.0.ico.")
    if pm3_workflow.count("Build validation executable") != 1:
        failures.append("pymobiledevice3 Auto Update workflow must contain exactly one validation build step.")

    if (ROOT / "version_info.txt").exists():
        failures.append("Legacy version_info.txt should not exist in the current source tree.")

    return failures


def audit_live_releases(tags: list[str]) -> list[str]:
    failures: list[str] = []
    url = "https://api.github.com/repos/DickyR15/DPort/releases?per_page=100"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "DPort-Full-Audit"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        releases = json.load(response)

    stable = [
        r
        for r in releases
        if not r.get("draft")
        and not r.get("prerelease")
        and re.fullmatch(r"v\d+\.\d+\.\d+", str(r.get("tag_name", "")))
    ]
    stable.sort(key=lambda r: tuple(int(x) for x in r["tag_name"][1:].split(".")), reverse=True)

    if not stable:
        return ["No stable releases found."]

    latest = stable[0]["tag_name"]
    print("GitHub highest stable release:", latest)

    for tag in tags:
        release = next((r for r in stable if r.get("tag_name") == tag), None)
        if not release:
            failures.append(f"Release {tag} is missing.")
            continue
        assets = {str(a.get("name")) for a in release.get("assets", [])}
        expected = {
            f"DPort-{tag[1:]}.exe",
            f"DPort-{tag[1:]}.exe.sha256",
            "DPort-Updater.exe",
            "DPort-Updater.exe.sha256",
        }
        missing = expected - assets
        if missing:
            failures.append(f"{tag} missing assets: {sorted(missing)}")

    return failures

def main() -> int:
    failures: list[str] = []
    try:
        tags = get_stable_release_tags(limit=2)
    except Exception as exc:
        print(f"Unable to discover stable release tags: {exc}")
        tags = []
        failures.append(f"Stable release discovery failed: {exc}")

    # Keep the exact starting commit so the audit is safe to run in a detached HEAD
    # environment such as GitHub Actions tag builds.
    original_ref = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()

    try:
        if not tags:
            failures.append("No stable release tags available for audit.")
        else:
            for tag in tags:
                failures.extend(audit_tag(tag))
        try:
            if tags:
                failures.extend(audit_live_releases(tags))
        except Exception as exc:
            failures.append(f"Live GitHub release audit failed: {exc}")
    finally:
        if original_ref:
            subprocess.run(
                ["git", "switch", "--detach", "--force", original_ref],
                cwd=ROOT,
                check=False,
            )

    # Return to the submitted ref before auditing current build tooling.
    subprocess.run(
        ["git", "switch", "--detach", "--force", original_ref],
        cwd=ROOT,
        check=False,
    )
    failures.extend(audit_current_source())

    print("=" * 70)
    if failures:
        print("FULL AUDIT FAILED")
        for item in failures:
            print(" -", item)
        return 1

    print("FULL AUDIT PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
