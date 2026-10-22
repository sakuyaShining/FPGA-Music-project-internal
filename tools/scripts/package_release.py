"""Create a versioned, allowlisted snapshot; never mark missing work complete."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]


def inside(path, root=ROOT):
    path = path.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"Path outside intended directory: {path}")
    return path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return p.stdout.decode("utf-8", errors="replace").strip() if p.returncode == 0 else None


def select(config, status, submission):
    selected = {}

    def add(src, dst):
        source = inside(ROOT / src)
        if not source.is_file():
            raise ValueError(f"Required file missing: {src}")
        if Path(dst).is_absolute() or ".." in Path(dst).parts:
            raise ValueError(f"Unsafe destination: {dst}")
        if dst in selected and selected[dst] != source:
            raise ValueError(f"Duplicate package destination: {dst}")
        selected[dst] = source

    for pattern in config["code_patterns"]:
        matches = [p for p in ROOT.glob(pattern) if p.is_file()]
        if not matches:
            raise ValueError(f"Allowlist matched nothing: {pattern}")
        for p in matches:
            relative = p.relative_to(ROOT).as_posix()
            if relative not in config["exclude"]:
                add(relative, "code/" + relative)
    for src, dst in config["documents"].items():
        add(src, dst)
        # Preserve inputs needed if the packager is run from exported code/.
        add(src, "code/" + src)
    evidence_missing = []
    for src, dst in config["evidence"].items():
        if (ROOT / src).is_file():
            add(src, dst)
        else:
            evidence_missing.append(src)

    project = inside(ROOT / config["project"])
    for entry in ET.parse(project).findall("./FileList/File"):
        source = inside(project.parent / entry.attrib["path"])
        destination = "code/" + source.relative_to(ROOT).as_posix()
        if destination not in selected:
            raise ValueError(f"Project dependency absent from package: {destination}")
    for filename in config["required_hex"]:
        required = "code/" + project.parent.relative_to(ROOT).as_posix() + "/" + filename
        if required not in selected:
            raise ValueError(f"Static table absent from package: {required}")

    if submission:
        missing = []
        if not status.get("submission_rules_verified"):
            missing.append("2026 submission rules verification")
        if status.get("stage") != "accepted_release":
            missing.append("accepted_release stage")
        for name, suffix in [("report", ".pdf"), ("demo_video", ".mp4"), ("authorization", ".pdf")]:
            src = status.get(name)
            if not src or not (ROOT / src).is_file() or Path(src).suffix.lower() != suffix:
                missing.append(name)
            else:
                add(src, "submission/" + name + suffix)
        for name in ["full_regression", "integrated_pnr", "board_audio", "end_to_end_latency", "real_multitouch", "cold_start"]:
            item = status.get("acceptance", {}).get(name)
            if not isinstance(item, dict) or item.get("result") != "pass" or not item.get("reviewed_by") or not item.get("evidence"):
                missing.append(name)
            elif not (ROOT / item["evidence"]).is_file():
                missing.append(name + " evidence file")
            else:
                add(item["evidence"], "evidence/final/" + name + Path(item["evidence"]).suffix)
        for name in ["bom", "wiring"]:
            src = status.get("hardware_files", {}).get(name)
            if not src or not (ROOT / src).is_file():
                missing.append("hardware " + name)
            else:
                add(src, "hardware/" + name + Path(src).suffix)
        if missing:
            raise ValueError("Formal release blocked: " + "; ".join(missing))
    return selected, evidence_missing


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True)
    ap.add_argument("--submission", action="store_true")
    ap.add_argument("--check", action="store_true", help="Validate only; write nothing")
    args = ap.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", args.version):
        raise ValueError("Use a short lowercase version starting with a letter")
    if args.version.split(".")[0].lower() in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}:
        raise ValueError("Reserved directory name")
    config = read_json(ROOT / "delivery/package.json")
    status = read_json(ROOT / "delivery/status.json")
    selected, missing = select(config, status, args.submission)
    print(f"Allowlist OK: {len(selected)} files; top={config['top_module']}; evidence unavailable={len(missing)}")
    if args.check:
        return
    release_root = ROOT / "release"
    target = inside(release_root / args.version)
    archive = inside(release_root / (args.version + ".zip"))
    if target.exists() or archive.exists():
        raise ValueError("Version already exists; choose a new version (no overwrite)")
    manifest = {
        "schema_version": 1, "version": args.version,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": status["stage"], "formal_submission_ready": bool(args.submission),
        "git_head": git("rev-parse", "HEAD"), "git_status": git("status", "--porcelain"),
        "git_diff_sha256": hashlib.sha256((git("diff", "HEAD", "--", "src", "tools", "delivery", "HANDOFF.md") or "").encode()).hexdigest(),
        "project": config["project"], "top_module": config["top_module"], "device": config["device"],
        "baseline_evidence_revision": status["baseline_evidence_revision"],
        "validation_status": status["acceptance"], "missing_optional_evidence": missing,
        "python_version": platform.python_version(), "python_packages": {}, "files": []
    }
    for name in ["numpy", "PyQt5", "pyserial"]:
        try:
            manifest["python_packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            manifest["python_packages"][name] = None
    target.mkdir(parents=True)
    for dst, source in sorted(selected.items()):
        dest = inside(target / dst, target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        manifest["files"].append({"path": dst, "source": source.relative_to(ROOT).as_posix(), "sha256": sha(dest), "bytes": dest.stat().st_size})
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with ZipFile(archive, "w", ZIP_DEFLATED) as z:
        for file in sorted(target.rglob("*")):
            if file.is_file():
                z.write(file, args.version + "/" + file.relative_to(target).as_posix())
    with ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError("Archive integrity check failed")
    print(f"Created {target.relative_to(ROOT)} and {archive.relative_to(ROOT)}; stage={status['stage']}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, ET.ParseError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
