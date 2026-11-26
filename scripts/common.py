"""Small shared helpers used by the numbered pipeline scripts."""

from pathlib import Path
import re

import pandas as pd

from config import OUTPUT_DIR


def require_file(path: Path, required_columns=()) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Required input file does not exist: {path}")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = sorted(set(required_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
    return frame


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    ensure_parent(path)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def normalize_keyword(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def record_attrition(step: str, rows_in: int, rows_out: int, reason: str) -> None:
    """Upsert one attrition record per step so reruns do not duplicate the log."""
    path = OUTPUT_DIR / "attrition.csv"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    columns = ["step", "rows_in", "rows_out", "rows_removed", "reason"]
    new_record = {
        "step": step,
        "rows_in": int(rows_in),
        "rows_out": int(rows_out),
        "rows_removed": int(rows_in - rows_out),
        "reason": reason,
    }
    if path.exists():
        existing = pd.read_csv(path, dtype=str, keep_default_na=False)
        if set(columns).issubset(existing.columns):
            existing = existing.loc[existing["step"] != step, columns]
            existing = pd.concat([existing, pd.DataFrame([new_record])], ignore_index=True)
        else:
            existing = pd.DataFrame([new_record])
    else:
        existing = pd.DataFrame([new_record])
    existing = existing.sort_values("step")
    write_csv(existing[columns], path)


def bool_value(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}
