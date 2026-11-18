# -*- coding: utf-8 -*-
"""模型标识归一化：把同一模型的多个批次运行归并到同一个规范模型 ID。

支持可读批次后缀，例如：
    deepseek-v4.1-flash-1017-h1
    deepseek-v4.1-flash-1017-s1
    gemini-4-carbon（Max）-run1

汇总时剥离末尾已知批次后缀（-h1 / -s1 / -batch1 / -run1 / -trial1 等），
同时保留模型本身的版本与推理强度标识（如 -r1、-v2、（Max））。
"""
from __future__ import annotations

import re

_BATCH_SUFFIX_RE = re.compile(
    r"-(?:"
    r"(?:h|s)(?:[-_]?\d+)?"
    r"|(?!(?:v|ver|r)[-_]?\d+$)[a-z](?:[-_]?\d+)"
    r"|(?:batch|run|round|trial|seed|rep|repeat)(?:[-_]?\d+)?"
    r")$",
    re.IGNORECASE,
)


def canonical_model_id(name: str) -> str:
    """返回排行榜分组与裁决留档使用的规范小写模型 ID。"""
    text = (name or "").strip()
    if not text:
        return ""
    stripped = _BATCH_SUFFIX_RE.sub("", text)
    return (stripped or text).lower()


def sanitize_run_name(name: str) -> str:
    """校验并清理运行目录名称，禁止路径穿越字符。"""
    cleaned = (name or "").strip()
    if not cleaned or any(ch in cleaned for ch in ("/", "\\", "..", ":")):
        raise ValueError(f"非法模型或运行名称: {name!r}")
    return cleaned


def matches_batch_run(model_name: str, run_name: str) -> bool:
    """判断 run_name 是否归属于显式指定的批次模型名 model_name。"""
    m = (model_name or "").strip().lower()
    r = (run_name or "").strip().lower()
    if not m or not r:
        return False
    if r == m:
        return True
    if r.startswith(m + "-") or r.startswith(m + "_"):
        return True
    if m[-1].isalpha():
        return re.match(r"^" + re.escape(m) + r"\d+(?:[-_].*)?$", r) is not None
    return False
