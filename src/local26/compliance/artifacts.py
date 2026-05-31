from __future__ import annotations

from pathlib import Path


def write_artifacts(output_dir: str | Path | None, *, run_id: str, text: str, json_text: str | None = None) -> Path | None:
    if output_dir is None:
        return None
    root = Path(output_dir)
    target = root / run_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "report.txt").write_text(text + "\n", encoding="utf-8")
    if json_text is not None:
        (target / "summary.json").write_text(json_text + "\n", encoding="utf-8")
    return target
