"""core/metrics.py —— 6 大指标计算 + 行级预警判定。

6 大指标（预警全部按绝对值判定）：
- 单次位移 / 单次沉降：优先用报表自带的「阶段（本次）变化量」列（ΔS = 单次位移、ΔH = 单次沉降）；
  缺失的行才用累计差 ÷ 相隔天数 推算（多日数据才行）。
- 累计位移 / 累计沉降：直接取报表「累计变化量」列。
- 水平位移速率 / 垂直位移速率（mm/天）：报表自带速率列优先；
  没有自带值时 = 单次变化量 ÷ 相隔天数（首期/单日没有相隔天数按 1 天计，此时速率 = 当天单次值）。
预警等级 = 6 项指标（累计×30mm，单次/速率×15mm）按绝对值取最严重（绿/黄/红）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.rules import level_of

VALUE_COLS = ["单次位移", "单次沉降", "累计位移", "累计沉降",
              "水平位移速率", "垂直位移速率"]


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """计算每个测点每期的 6 大指标，并逐行判定预警等级。"""
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["日期"]):
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df = df.dropna(subset=["日期"])
    if df.empty:
        raise ValueError("数据里没有有效日期，请回到第 1 页重新上传数据。")

    for c in VALUE_COLS:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 同一测点同一天出现多条记录时取平均，保证每个点每天只有一行
    df = df.groupby(["测点编号", "日期"], as_index=False)[VALUE_COLS].mean()

    out = []
    for pid, g in df.groupby("测点编号"):
        g = g.sort_values("日期").reset_index(drop=True)
        days = (g["日期"] - g["日期"].shift(1)).dt.total_seconds() / 86400.0
        days = days.replace(0, np.nan)          # 相隔 0 天没有意义，避免除零
        calc_ds = (g["累计位移"] - g["累计位移"].shift(1)) / days
        calc_dh = (g["累计沉降"] - g["累计沉降"].shift(1)) / days
        # 单次：报表自带阶段变化量优先，缺失的行用推算值补上
        g["单次位移"] = g["单次位移"].where(g["单次位移"].notna(), calc_ds)
        g["单次沉降"] = g["单次沉降"].where(g["单次沉降"].notna(), calc_dh)
        # 速率：报表自带速率列优先，缺失的行 = 单次 ÷ 相隔天数（首期/单日按 1 天）
        days_eff = days.fillna(1.0)
        g["水平位移速率"] = g["水平位移速率"].where(
            g["水平位移速率"].notna(), g["单次位移"] / days_eff)
        g["垂直位移速率"] = g["垂直位移速率"].where(
            g["垂直位移速率"].notna(), g["单次沉降"] / days_eff)
        out.append(g)
    m = pd.concat(out, ignore_index=True)

    m["预警等级"] = [
        level_of(a, b, c, d, e, f)
        for a, b, c, d, e, f in zip(m["累计位移"], m["单次位移"], m["累计沉降"],
                                    m["单次沉降"], m["水平位移速率"], m["垂直位移速率"])
    ]
    return m[["测点编号", "日期"] + VALUE_COLS + ["预警等级"]]
