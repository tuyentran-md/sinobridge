"""Atomic project storage; source text and model outputs never auto-commit."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def save_json(path: Path, value: object) -> None:
    save_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def save_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp_name = handle.name
    os.replace(temp_name, path)

def save_segments(directory: Path, segments: list[dict]) -> None:
    save_text(directory / "segments.jsonl", "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in segments))

def load_segments(directory: Path) -> list[dict]:
    path = directory / "segments.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"No translation project at {directory}; run 'ingest' first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def load_project(directory: Path) -> dict:
    return json.loads((directory / "project.json").read_text(encoding="utf-8"))
