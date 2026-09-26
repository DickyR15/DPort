import argparse
import re
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


def bump_patch(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid DPort version: {version}")
    parts[2] = str(int(parts[2]) + 1)
    return ".".join(parts)




def replace_pm3(text: str, version: str) -> str:
    pattern = r"(?mi)^\s*pymobiledevice3\s*==\s*[^\s#]+"
    if not re.search(pattern, text):
        raise RuntimeError("pymobiledevice3 pin not found")
    return re.sub(pattern, f"pymobiledevice3=={version}", text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True)
    parser.add_argument("--latest-pm3", required=True)
    parser.add_argument("--output-version", required=True)
    args = parser.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.exists():
        raise SystemExit(f"Missing source ZIP: {zip_path}")

    root_name = "DPort-6.9.0"

    with TemporaryDirectory() as td:
        td = Path(td)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(td)

        root = td / root_name
        version_file = root / "src" / "dport_version.py"
        req_file = root / "requirements-build.txt"
        if not version_file.exists():
            raise SystemExit("Source ZIP is missing src/dport_version.py")
        if not req_file.exists():
            raise SystemExit("Source ZIP is missing requirements-build.txt")

        current_text = version_file.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'DPORT_VERSION\s*=\s*["\']([^"\']+)["\']', current_text)
        if not match:
            raise SystemExit("DPORT_VERSION not found in source package")

        current_version = match.group(1)
        expected = bump_patch(current_version)
        if expected != args.output_version:
            raise SystemExit(
                f"Version mismatch: source implies {expected}, requested {args.output_version}"
            )

        version_file.write_text(
            f'DPORT_VERSION="{args.output_version}"\n',
            encoding="utf-8",
        )

        req_text = req_file.read_text(encoding="utf-8", errors="replace")
        req_file.write_text(
            replace_pm3(req_text, args.latest_pm3),
            encoding="utf-8",
        )

        updater_file = root / "src" / "dport_release_updater.py"
        if not updater_file.exists():
            raise SystemExit("Source ZIP is missing src/dport_release_updater.py")

        tmp_zip = zip_path.with_suffix(".new.zip")
        if tmp_zip.exists():
            tmp_zip.unlink()

        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in root.rglob("*"):
                if path.is_file():
                    arcname = Path(root_name) / path.relative_to(root)
                    zf.write(path, arcname.as_posix())

        tmp_zip.replace(zip_path)

    repo_req = Path("requirements-build.txt")
    if repo_req.exists():
        repo_text = repo_req.read_text(encoding="utf-8", errors="replace")
        repo_req.write_text(replace_pm3(repo_text, args.latest_pm3), encoding="utf-8")
    else:
        repo_req.write_text(f"pymobiledevice3=={args.latest_pm3}\n", encoding="utf-8")

    Path("src/dport_version.py").write_text(
        f'DPORT_VERSION="{args.output_version}"\n',
        encoding="utf-8",
    )

    print(f"Updated DPort to {args.output_version}")
    print(f"Updated pymobiledevice3 to {args.latest_pm3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
