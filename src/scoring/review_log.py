# -*- coding: utf-8 -*-
"""中心化、追加式盲评日志（leaderboard/reviews.jsonl）与运行生命周期台账读写工具。"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import datetime
import json
import os
import statistics
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_LOG = Path(os.environ.get("CH_REVIEW_LOG") or (ROOT / "leaderboard" / "reviews.jsonl"))
DEFAULT_RUNS_LOG = Path(os.environ.get("CH_RUNS_LOG") or (ROOT / "leaderboard" / "runs_log.jsonl"))

SCHEMA_VERSION = 1
REQUIRED = (
    "schema_version",
    "review_id",
    "created_at",
    "judge_id",
    "judge_model",
    "pack_id",
    "case_id",
    "D1",
    "D2",
    "D3",
)
D_RANGES = {
    "D1": (0.0, 10.0),
    "D2": (0.0, 10.0),
    "D3": (0.0, 10.0),
}


class ReviewLogError(Exception):
    """评审日志校验或读写异常。"""


class DuplicateReviewError(ReviewLogError):
    """同一评委对同一匿名包 case 重复提交异常。"""


@contextmanager
def file_lock(target_path: Path, timeout: float = 15.0):
    """基于原子排他锁文件的跨进程写入保护。"""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target_path.with_suffix(target_path.suffix + ".lock")
    deadline = time.time() + timeout
    fd = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.time() > deadline:
                raise ReviewLogError(f"日志文件锁定超时：{lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def validate_review(rec: dict) -> bool:
    if not isinstance(rec, dict):
        raise ReviewLogError("评审记录必须是 JSON 对象")
    missing = [k for k in REQUIRED if k not in rec]
    if missing:
        raise ReviewLogError("评审记录缺少字段: " + ", ".join(missing))
    if int(rec.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ReviewLogError(f"schema_version 必须是 {SCHEMA_VERSION}")
    for k in ("review_id", "created_at", "judge_id", "judge_model", "pack_id", "case_id"):
        if not isinstance(rec.get(k), str) or not rec[k].strip():
            raise ReviewLogError(f"{k} 必须是非空字符串")
    for k, (lo, hi) in D_RANGES.items():
        v = rec.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not (lo <= float(v) <= hi):
            raise ReviewLogError(f"{k} 必须在 [{lo}, {hi}] 范围内")
    return True


def read_reviews(log_path: str | Path | None = None) -> list[dict]:
    path = Path(log_path or DEFAULT_LOG)
    if not path.exists():
        return []
    out = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception as e:
            raise ReviewLogError(f"{path}:{lineno}: 非法 JSON：{e}") from e
        try:
            validate_review(rec)
        except ReviewLogError as e:
            raise ReviewLogError(f"{path}:{lineno}: {e}") from e
        out.append(rec)
    return out


def dedupe_latest(reviews: list[dict]) -> tuple[list[dict], int]:
    """同一 (pack_id, case_id, judge_id) 仅保留最新提交的一条。"""
    by_key: dict[tuple[str, str, str], dict] = {}
    for rec in reviews:
        key = (rec["pack_id"], rec["case_id"], rec["judge_id"])
        prev = by_key.get(key)
        if prev is None or str(rec.get("created_at", "")) >= str(prev.get("created_at", "")):
            by_key[key] = rec
    return list(by_key.values()), len(reviews) - len(by_key)


def aggregate_reviews(reviews: list[dict], mode: str = "mean") -> list[dict]:
    """按 (pack_id, case_id) 聚合多位评委的 D1/D2/D3 评分。"""
    if mode not in ("mean", "median"):
        raise ReviewLogError("mode 只能是 mean 或 median")
    groups: dict[tuple[str, str], list[dict]] = {}
    for rec in reviews:
        groups.setdefault((rec["pack_id"], rec["case_id"]), []).append(rec)
    out = []
    for (pack_id, case_id), items in sorted(groups.items()):
        dims = {}
        for dim in ("D1", "D2", "D3"):
            vals = [float(x[dim]) for x in items]
            dims[dim] = round(statistics.mean(vals) if mode == "mean" else statistics.median(vals), 2)
        out.append(
            {
                "pack_id": pack_id,
                "case_id": case_id,
                "judge_count": len(items),
                "D1": dims["D1"],
                "D2": dims["D2"],
                "D3": dims["D3"],
                "D": round(dims["D1"] + dims["D2"] + dims["D3"], 2),
                "review_ids": [x.get("review_id") for x in items],
                "judges": [
                    {
                        "judge_id": x.get("judge_id"),
                        "judge_model": x.get("judge_model"),
                        "created_at": x.get("created_at"),
                        "D1": x.get("D1"),
                        "D2": x.get("D2"),
                        "D3": x.get("D3"),
                        "evidence": x.get("evidence", ""),
                        "note": x.get("note", ""),
                    }
                    for x in items
                ],
            }
        )
    return out


def append_review(log_path: str | Path | None, record: dict, reject_duplicate: bool = True) -> dict:
    """原子追加单条评审记录；默认拒绝同一评委重复提交同一 case。"""
    path = Path(log_path or DEFAULT_LOG)
    rec = dict(record)
    rec.setdefault("schema_version", SCHEMA_VERSION)
    rec.setdefault("review_id", str(uuid.uuid4()))
    rec.setdefault("created_at", datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
    rec["D1"] = round(float(rec["D1"]), 2)
    rec["D2"] = round(float(rec["D2"]), 2)
    rec["D3"] = round(float(rec["D3"]), 2)
    rec["total"] = round(rec["D1"] + rec["D2"] + rec["D3"], 2)
    validate_review(rec)
    with file_lock(path):
        existing = read_reviews(path)
        if reject_duplicate:
            key = (rec["pack_id"], rec["case_id"], rec["judge_id"])
            if any((x["pack_id"], x["case_id"], x["judge_id"]) == key for x in existing):
                raise DuplicateReviewError(
                    f"该评委（{rec['judge_id']}）已提交过 pack={rec['pack_id']} case={rec['case_id']}；"
                    "如需更正请联系汇总者，请勿重复提交。"
                )
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
    return rec


def append_run_event(event_type: str, payload: dict, log_path: str | Path | None = None) -> dict:
    """向 leaderboard/runs_log.jsonl 追加运行生命周期审计记录（start / pack / finalize）。"""
    path = Path(log_path or DEFAULT_RUNS_LOG)
    entry = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "event_type": event_type,
        **payload,
    }
    with file_lock(path):
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
    return entry
