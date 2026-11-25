#!/usr/bin/env python3
"""Build release ZIPs, RELEASE-MANIFEST.json and SHA256SUMS from the committed HEAD."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "research-notebook-agent-skills"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True).stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for the assets")
    output = parser.parse_args().output_dir.resolve()
    if git("status", "--porcelain").strip():
        raise SystemExit("BLOCKED: commit or remove local changes; assets are built from HEAD only")
    commit = git("rev-parse", "HEAD").decode().strip()
    files = {name: git("show", f"{commit}:{name}")
             for name in git("ls-tree", "-r", "--name-only", "-z", commit).decode().split("\0") if name}
    skills = sorted(name.split("/")[0] for name in files if re.fullmatch(r"[^/]+/SKILL\.md", name))
    versions = {re.search(r'^  version: "([^"]+)"$', files[f"{skill}/SKILL.md"].decode(), re.M).group(1) for skill in skills}
    if len(versions) != 1:
        raise SystemExit(f"BLOCKED: skill versions differ: {sorted(versions)}")
    version = versions.pop()
    # Fixed timestamps and order make the same commit produce the same archive contents.
    stamp = tuple(int(x) for x in git("show", "-s", "--format=%cd", "--date=format:%Y %m %d %H %M %S", commit).split())
    packages = {skill: {name: data for name, data in files.items() if name.startswith(skill + "/")} for skill in skills}
    for skill in skills:
        packages[skill][f"{skill}/LICENSE"] = files["LICENSE"]
    packages[NAME] = {f"{NAME}/{name}": data for name, data in files.items()
                      if not name.startswith((".github/", ".gitignore"))}
    output.mkdir(parents=True, exist_ok=False)
    assets = []
    for package, content in packages.items():
        path = output / f"{package}-{version}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(content):
                info = zipfile.ZipInfo(name, stamp)
                info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
                archive.writestr(info, content[name])
        assets.append({"file": path.name, "sha256": digest(path), "bytes": path.stat().st_size})
    manifest = output / "RELEASE-MANIFEST.json"
    manifest.write_text(json.dumps({"version": version, "commit": commit, "assets": assets}, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS").write_text("".join(f"{digest(output / name)}  {name}\n" for name in
                                               [x["file"] for x in assets] + [manifest.name]), encoding="utf-8")
    print(f"Built {version} from {commit[:7]} in {output}")


if __name__ == "__main__":
    main()
