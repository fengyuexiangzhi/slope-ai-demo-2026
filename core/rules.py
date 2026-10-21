"""core/rules.py —— 三级预警判定规则（双控指标）与统计汇总。

双控指标（本规则的唯一标准）：
- 累计变化量限度 30mm：|值|≤30 绿；(30, 45] 黄；>45 红
- 单次变化量与速率限度 15mm：|值|≤15 绿；(15, 22.5] 黄；>22.5 红
一个点位/一行数据的最终级别 = 六项指标（累计位移、累计沉降、单次位移、单次沉降、
水平位移速率、垂直位移速率）按绝对值取最严重的级别。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---- 双控阈值（毫米） ----
CUM_LIMIT = 30.0      # 累计变化量限度
DAILY_LIMIT = 15.0    # 单日变化量限度
YELLOW_FACTOR = 1.5   # 超过限度的 50%（即 1.5 倍）升级为红色

LEVEL_ORDER = ["绿", "黄", "红"]
LEVEL_COLORS = {"绿": "#2e9e44", "黄": "#f2c313", "红": "#e03131"}
LEVEL_EMOJI = {"绿": "🟢", "黄": "🟡", "红": "🔴"}
LEVEL_DESC = {
    "绿": "绿色：各项指标均在限度内（累计≤30mm 且 单次≤15mm）",
    "黄": "黄色：已超限但未超限度的50%（累计30~45mm 或 单次15~22.5mm）",
    "红": "红色：超过限度的50%以上（累计>45mm 或 单次>22.5mm）",
}

_LEVEL_RANK = {"绿": 0, "黄": 1, "红": 2}


def level_of_value(value, limit) -> str:
    """单指标判定：≤限度为绿；(限度, 1.5×限度] 为黄；超过 1.5×限度 为红。空值视为绿。"""
    if value is None or pd.isna(value):
        return "绿"
    v = abs(float(value))
    if v <= limit:
        return "绿"
    if v <= limit * YELLOW_FACTOR:
        return "黄"
    return "红"


def worst(*levels) -> str:
    """取多个级别中最严重的。"""
    result = "绿"
    for lv in levels:
        if lv is not None and _LEVEL_RANK.get(lv, 0) > _LEVEL_RANK[result]:
            result = lv
    return result


def level_of(cum_disp=None, daily_disp=None, cum_settle=None, daily_settle=None,
             rate_h=None, rate_v=None) -> str:
    """最终预警级别：六项指标按绝对值取最严重。

    累计位移/累计沉降 按 30mm 限度；单次位移/单次沉降/水平速率/垂直速率 按 15mm 限度。
    """
    return worst(
        level_of_value(cum_disp, CUM_LIMIT),
        level_of_value(daily_disp, DAILY_LIMIT),
        level_of_value(cum_settle, CUM_LIMIT),
        level_of_value(daily_settle, DAILY_LIMIT),
        level_of_value(rate_h, DAILY_LIMIT),
        level_of_value(rate_v, DAILY_LIMIT),
    )


def _over(value, limit) -> bool:
    """该指标是否超过限度。"""
    try:
        if value is None or pd.isna(value):
            return False
        return bool(abs(float(value)) > limit)
    except Exception:
        return False


def _round(x, n):
    """安全地保留 n 位小数，空值返回 None。"""
    try:
        if pd.isna(x):
            return None
        return round(float(x), n)
    except Exception:
        return None


def summarize(metrics: pd.DataFrame) -> dict:
    """统计摘要：每个点位的最新累计值、时段最大单次变化量与速率、超限情况、最终预警颜色。

    最终预警 = 六项指标（累计位移/累计沉降按 30mm，单次与速率按 15mm）中最严重者。
    """
    per_point = []
    for pid, g in metrics.groupby("测点编号"):
        g = g.sort_values("日期")
        last = g.iloc[-1]

        def _max(col):
            """时段内绝对值最大的一条（保留原始正负号，危险不看方向）。"""
            if col not in g.columns:
                return np.nan
            s = g[col].dropna()
            if s.empty:
                return np.nan
            return s.loc[s.abs().idxmax()]

        max_ds = _max("单次位移")
        max_dh = _max("单次沉降")
        max_rh = _max("水平位移速率")
        max_rv = _max("垂直位移速率")
        per_point.append({
            "测点编号": str(pid),
            "监测期数": int(len(g)),
            "最新日期": str(pd.Timestamp(last["日期"]).date()),
            "最新累计位移": _round(last["累计位移"], 2),
            "累计位移超限": _over(last["累计位移"], CUM_LIMIT),
            "最大单次位移": _round(max_ds, 2),
            "单次位移超限": _over(max_ds, DAILY_LIMIT),
            "最新累计沉降": _round(last["累计沉降"], 2),
            "累计沉降超限": _over(last["累计沉降"], CUM_LIMIT),
            "最大单次沉降": _round(max_dh, 2),
            "单次沉降超限": _over(max_dh, DAILY_LIMIT),
            "最大水平位移速率": _round(max_rh, 2),
            "最大垂直位移速率": _round(max_rv, 2),
            "速率超限": _over(max_rh, DAILY_LIMIT) or _over(max_rv, DAILY_LIMIT),
            "最终预警": level_of(last["累计位移"], max_ds, last["累计沉降"],
                                 max_dh, max_rh, max_rv),
        })
    dist = {lv: sum(1 for p in per_point if p["最终预警"] == lv) for lv in LEVEL_ORDER}
    n_dates = int(metrics["日期"].nunique())
    return {
        "数据模式": "多日" if n_dates > 1 else "单日",
        "监测日期数": n_dates,
        "测点数": int(metrics["测点编号"].nunique()),
        "记录条数": int(len(metrics)),
        "日期范围": [str(metrics["日期"].min().date()), str(metrics["日期"].max().date())],
        "等级分布": dist,
        "测点明细": per_point,
    }


def _fmt(v) -> str:
    """数值转文案，空值显示“无数据”。"""
    return "无数据" if v is None else f"{v}"


def stats_to_text(stats: dict) -> str:
    """把统计摘要转成中文文本（喂给 AI 用），突出三要素：累计超限/单日超限/最终预警颜色。"""
    lines = [
        f"监测模式：{stats['数据模式']}（{stats['监测日期数']} 个监测日期，"
        f"{stats['日期范围'][0]} 至 {stats['日期范围'][1]}）；"
        f"测点 {stats['测点数']} 个，数据 {stats['记录条数']} 条。",
        f"预警规则（双控指标）：累计变化量限度 {CUM_LIMIT:g}mm、单次变化量限度 {DAILY_LIMIT:g}mm；"
        f"超过限度 50%（累计 >{CUM_LIMIT * 1.5:g}mm 或 单次 >{DAILY_LIMIT * 1.5:g}mm）为红色预警。",
        "最终预警分布：" + "、".join(
            f"{LEVEL_EMOJI[lv]}{lv}色 {stats['等级分布'][lv]} 个测点" for lv in LEVEL_ORDER) + "。",
        "各测点明细（单位 mm；“超限”指超过对应限度）：",
    ]
    for p in stats["测点明细"]:
        parts = [
            f"测点{p['测点编号']}：最新累计位移 {_fmt(p['最新累计位移'])}mm（"
            f"{'超限' if p['累计位移超限'] else '未超限'}）",
            f"最新累计沉降 {_fmt(p['最新累计沉降'])}mm（{'超限' if p['累计沉降超限'] else '未超限'}）",
        ]
        if p["最大单次位移"] is not None:
            parts.append(f"最大单次位移 {_fmt(p['最大单次位移'])}mm（"
                         f"{'超限' if p['单次位移超限'] else '未超限'}）")
        if p["最大单次沉降"] is not None:
            parts.append(f"最大单次沉降 {_fmt(p['最大单次沉降'])}mm（"
                         f"{'超限' if p['单次沉降超限'] else '未超限'}）")
        if p["最大水平位移速率"] is not None or p["最大垂直位移速率"] is not None:
            parts.append(f"最大水平/垂直速率 {_fmt(p['最大水平位移速率'])}/"
                         f"{_fmt(p['最大垂直位移速率'])}mm/天（"
                         f"{'超限' if p['速率超限'] else '未超限'}）")
        parts.append(f"最终预警【{LEVEL_EMOJI[p['最终预警']]}{p['最终预警']}色】")
        lines.append("- " + "，".join(parts) + "。")
    return "\n".join(lines)
