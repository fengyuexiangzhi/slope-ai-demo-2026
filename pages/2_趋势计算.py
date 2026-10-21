"""② 趋势计算页（三级预警 · 双控指标）"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from core.metrics import compute_metrics
from core.rules import LEVEL_DESC, LEVEL_EMOJI, LEVEL_ORDER, summarize
from core.style import apply_theme

st.set_page_config(page_title="② 趋势计算", page_icon="📈", layout="wide")
apply_theme()
st.title("📈 第 2 步：趋势计算与预警判定")
st.caption("按双控指标判定三级预警：累计变化量限度 **30mm**、单次变化量限度 **15mm**；"
           "取各项指标中最严重的级别作为该点位的最终级别。")

if st.session_state.get("df") is None:
    st.warning("还没有数据，请先到左侧「① 数据上传」上传文件或生成示例数据。")
    st.stop()

try:
    with st.spinner("正在计算……"):
        m = compute_metrics(st.session_state.df)
except Exception as e:
    st.error(f"计算失败：{e}")
    st.stop()

st.session_state.metrics = m
stats = summarize(m)

st.success(
    f"计算完成！共 {stats['记录条数']} 条记录、{stats['测点数']} 个测点、"
    f"{stats['监测日期数']} 个监测日期（{stats['日期范围'][0]} 至 {stats['日期范围'][1]}）。"
    + ("" if stats["数据模式"] == "多日" else "当前是单日数据，只按累计值判定。")
)

st.subheader("最终预警分布")
cols = st.columns(4)
labels = {
    "绿": f"{LEVEL_EMOJI['绿']} 绿色点位（稳定）",
    "黄": f"{LEVEL_EMOJI['黄']} 黄色点位（超限未超50%）",
    "红": f"{LEVEL_EMOJI['红']} 红色点位（超限超50%）",
}
for c, lv in zip(cols[:3], LEVEL_ORDER):
    c.metric(labels[lv], stats["等级分布"][lv])
cols[3].metric("测点总数", stats["测点数"])
st.caption("；".join(LEVEL_DESC[lv] for lv in LEVEL_ORDER) + "。")


def _over_mark(val, over) -> str:
    """把超限布尔值转成易读文字；没有数据的显示 —。"""
    if val is None:
        return "—"
    return "⚠️ 超限" if over else "✅ 正常"


detail = pd.DataFrame(stats["测点明细"])
if not detail.empty:
    detail["累计位移超限"] = [
        _over_mark(v, o) for v, o in zip(detail["最新累计位移"], detail["累计位移超限"])]
    detail["累计沉降超限"] = [
        _over_mark(v, o) for v, o in zip(detail["最新累计沉降"], detail["累计沉降超限"])]
    detail["单次位移超限"] = [
        _over_mark(v, o) for v, o in zip(detail["最大单次位移"], detail["单次位移超限"])]
    detail["单次沉降超限"] = [
        _over_mark(v, o) for v, o in zip(detail["最大单次沉降"], detail["单次沉降超限"])]

st.subheader("各测点预警一览（空间对比：同一天不同点位横向对比）")
st.dataframe(detail, width="stretch", hide_index=True)
st.caption("「最新累计」= 该测点最新一天的累计变化量；「最大单次」= 该测点各期单次变化量的最大值"
           "（优先直接取报表自带的阶段变化量/本次变化量列，没有时显示 —）。")

st.subheader("全部明细（时间对比：同一点位不同日期纵向对比）")
st.dataframe(
    m,
    width="stretch",
    hide_index=True,
    column_config={"日期": st.column_config.DateColumn("日期", format="YYYY-MM-DD")},
)

csv = m.to_csv(index=False).encode("utf-8-sig")
st.download_button("下载计算结果 (csv)", csv, "预警计算结果.csv", "text/csv")

with st.expander("📘 预警规则（大白话）"):
    st.markdown(
        "- **累计变化量**：从开始监测到现在，点位一共挪了多少毫米。限度 **30mm**。\n"
        "- **单次变化量**：相邻两期之间的阶段变化量（优先直接用报表自带的「本次变化量」列）。"
        "限度 **15mm**。\n"
        f"- {LEVEL_EMOJI['绿']} **绿色**：累计 ≤ 30mm 且 单次 ≤ 15mm，一切正常。\n"
        f"- {LEVEL_EMOJI['黄']} **黄色**：超了限度，但没超限度的 50%"
        "（累计 30~45mm，或单次 15~22.5mm）。\n"
        f"- {LEVEL_EMOJI['红']} **红色**：超过限度的 50% 以上（累计 > 45mm，或单次 > 22.5mm），危险！\n"
        "- 一个点位的**最终颜色**：看它四项指标（累计位移、单次位移、累计沉降、单次沉降）里最严重的那项。"
    )
