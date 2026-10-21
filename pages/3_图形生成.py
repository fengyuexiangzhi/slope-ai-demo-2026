"""③ 图形生成页（测点数据一览表 + 6 大指标三图）"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.rules import (
    CUM_LIMIT, DAILY_LIMIT, LEVEL_COLORS, LEVEL_EMOJI, level_of_value, summarize,
)
from core.style import DARK_PLOTLY_LAYOUT, apply_theme

st.set_page_config(page_title="③ 图形生成", page_icon="📊", layout="wide")
apply_theme()
st.title("📊 第 3 步：图形生成")
st.caption("6 大指标全部按**绝对值**判定：🟢 |值|≤限度、🟡 限度<|值|≤1.5倍限度、🔴 |值|>1.5倍限度；"
           "单次/速率限度 15（mm 或 mm/天），累计限度 30mm。")

if st.session_state.get("metrics") is None:
    st.warning("还没有计算结果，请先到左侧「② 趋势计算」点一下。")
    st.stop()

m = st.session_state.metrics
n_dates = int(m["日期"].nunique())
is_multi = n_dates > 1

# 6 大指标：显示名 → (数据列名, 限度, 单位)。下拉框严格按此顺序。
METRIC_MAP = {
    "单次位移": ("单次位移", DAILY_LIMIT, "mm"),
    "单次沉降": ("单次沉降", DAILY_LIMIT, "mm"),
    "累计位移": ("累计位移", CUM_LIMIT, "mm"),
    "累计沉降": ("累计沉降", CUM_LIMIT, "mm"),
    "水平位移速率": ("水平位移速率", DAILY_LIMIT, "mm/天"),
    "垂直位移速率": ("垂直位移速率", DAILY_LIMIT, "mm/天"),
}

# ---------------- 测点数据一览表（列顺序严格固定） ----------------
st.subheader("📋 测点数据一览表（各测点最新一期）")
stats = summarize(m)
final_lv = {p["测点编号"]: p["最终预警"] for p in stats["测点明细"]}
latest = (m.sort_values("日期")
          .groupby("测点编号", as_index=False, sort=True)
          .tail(1)
          .sort_values("测点编号"))
overview = latest[["测点编号", "单次位移", "单次沉降", "累计位移", "累计沉降",
                   "水平位移速率", "垂直位移速率"]].copy()
overview["测点编号"] = overview["测点编号"].astype(str)
overview["最终预警级别"] = [
    f"{LEVEL_EMOJI[final_lv.get(pid, '绿')]}{final_lv.get(pid, '绿')}色"
    for pid in overview["测点编号"]
]

# 预警级别文字按级别着色（红色加粗标红，黄色高亮，绿色正常）
def _level_color(val):
    s = str(val)
    if "红色" in s:
        return "color:#ff5c5c;font-weight:700;"
    if "黄色" in s:
        return "color:#ffd54f;font-weight:600;"
    if "绿色" in s:
        return "color:#4ade80;"
    return ""

styled = overview.round(2).style.map(_level_color, subset=["最终预警级别"])
st.dataframe(styled, width="stretch", hide_index=True)
st.caption("速率为报表自带值或按「单次变化量 ÷ 相隔天数」计算（mm/天）。")

tab1, tab2, tab3 = st.tabs([
    "📊 图一：多测点对比图（柱状图）",
    "📈 图二：单测点时间趋势图（折线图）",
    "📉 图三：多点位速率对比图（折线图）",
])

# ---------------- 图一：多测点对比（空间对比：同一天不同点位） ----------------
with tab1:
    st.subheader("同一天不同点位的横向对比")
    metric = st.selectbox(
        "选择指标", list(METRIC_MAP.keys()),
        help="单次/速率类限度 15，累计类限度 30。"
             "柱色按绝对值判定：|值| ≤ 限度 绿；(限度, 1.5×限度] 黄；> 1.5×限度 红。")
    col, limit, unit = METRIC_MAP[metric]

    if is_multi:
        date_strs = sorted({pd.Timestamp(d).strftime("%Y-%m-%d") for d in m["日期"]})
        picked = st.selectbox("选择监测日期（默认最新一天）", date_strs,
                              index=len(date_strs) - 1)
        sub = m[m["日期"] == pd.Timestamp(picked)].sort_values("测点编号")
    else:
        sub = m.sort_values("测点编号")

    vals = pd.to_numeric(sub[col], errors="coerce").astype(float)
    if vals.notna().any():
        colors = [LEVEL_COLORS[level_of_value(v, limit)] for v in vals]
        fig = go.Figure(go.Bar(
            x=sub["测点编号"].astype(str),
            y=vals,
            marker_color=colors,
            text=[f"{v:.1f}" if pd.notna(v) else "" for v in vals],
            textposition="outside",
        ))
        # 警戒线双向画：0 轴上方 +限度/+1.5×限度，0 轴下方 -限度/-1.5×限度
        for y, color, label in (
            (limit, "#f2c313", f"+{limit:g} 警戒线"),
            (-limit, "#f2c313", f"-{limit:g} 警戒线"),
            (limit * 1.5, "#e03131", f"+{limit * 1.5:g} 红线"),
            (-limit * 1.5, "#e03131", f"-{limit * 1.5:g} 红线"),
        ):
            fig.add_hline(
                y=y, line_dash="dash", line_color=color, annotation_text=label,
                annotation_position="top left" if y > 0 else "bottom left",
                annotation_font_color="#ffd54f" if color == "#f2c313" else "#ff6b6b")
        peak = float(vals.abs().max())
        span = max(limit * 1.5, peak) * 1.25
        fig.update_layout(
            **DARK_PLOTLY_LAYOUT,
            xaxis_title="点号",
            yaxis_title=f"{metric}（{unit}）",
            showlegend=False,
            margin=dict(l=40, r=40, t=30, b=40),
            height=520,
        )
        fig.update_yaxes(range=[-span, span], zeroline=True, zerolinecolor="rgba(255,255,255,0.2)")
        st.plotly_chart(fig, width="stretch")
        st.caption(f"当前图：{metric}（限度 {limit:g}{unit}）。柱色按**绝对值**判定："
                   f"|值|≤{limit:g} 绿；{limit:g}~{limit * 1.5:g} 黄；>{limit * 1.5:g} 红，负值同理。"
                   "黄色虚线 = ±限度线，红色虚线 = ±1.5 倍限度线。")
    else:
        st.info(f"当前数据算不出「{metric}」：既没有报表自带列，也无法推算。"
                "请检查上传的数据里是否有对应的数值列。")

# ---------------- 图二：单点时间趋势（时间对比：同一点位不同日期） ----------------
with tab2:
    st.subheader("同一个点位在不同日期的纵向对比")
    if not is_multi:
        st.info("当前只有 **1 个监测日期** 的数据，画不了时间趋势图。"
                "把其它日期的报表也上传进来（第 1 步支持多选），就能看这张图了。")
    else:
        c1, c2 = st.columns(2)
        pids = sorted(m["测点编号"].astype(str).unique())
        pid = c1.selectbox("选择点号", pids)
        y_metric = c2.selectbox("选择 Y 轴指标", list(METRIC_MAP.keys()), index=2,
                                help="6 大指标任选；警戒线随指标自动切换（单次/速率 ±15，累计 ±30）。")
        y_col, y_limit, y_unit = METRIC_MAP[y_metric]
        g = m[m["测点编号"].astype(str) == pid].sort_values("日期")

        if g[y_col].notna().any():
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=g["日期"], y=g[y_col].astype(float), mode="lines+markers",
                name=y_metric, line=dict(color="#1f77b4", width=2.5)))
            # 警戒线双向画：±限度 与 ±1.5×限度
            for y, color, label in (
                (y_limit, "#f2c313", f"+{y_limit:g} 警戒线"),
                (-y_limit, "#f2c313", f"-{y_limit:g} 警戒线"),
                (y_limit * 1.5, "#e03131", f"+{y_limit * 1.5:g} 红线"),
                (-y_limit * 1.5, "#e03131", f"-{y_limit * 1.5:g} 红线"),
            ):
                fig.add_hline(
                    y=y, line_dash="dash", line_color=color, annotation_text=label,
                    annotation_position="top left" if y > 0 else "bottom left",
                    annotation_font_color="#ffd54f" if color == "#f2c313" else "#ff6b6b")
            peak = float(g[y_col].astype(float).abs().max())
            span = max(y_limit * 1.5, peak) * 1.25
            fig.update_layout(
                **DARK_PLOTLY_LAYOUT,
                hovermode="x unified",
                xaxis_title="时间",
                yaxis_title=f"{y_metric}（{y_unit}）",
                showlegend=False,
                margin=dict(l=40, r=40, t=30, b=40),
                height=520,
            )
            fig.update_yaxes(range=[-span, span], zeroline=True, zerolinecolor="rgba(255,255,255,0.2)")
            st.plotly_chart(fig, width="stretch")
            st.caption(f"{pid} 的「{y_metric}」时间趋势：黄色虚线 = ±{y_limit:g}{y_unit} 警戒线、"
                       f"红色虚线 = ±{y_limit * 1.5:g}{y_unit} 红线，曲线越任一侧即超限（按绝对值判定）。")
        else:
            st.info(f"{pid} 没有「{y_metric}」数据，换个指标试试。")

# ---------------- 图三：多点位速率对比（时间对比：所有点位一张图） ----------------
with tab3:
    st.subheader("不同点位的速率变化趋势对比")
    rate_label = st.selectbox(
        "选择速率指标", ["水平位移速率", "垂直位移速率"],
        help="速率 = 单次变化量 ÷ 相隔天数（mm/天）；每天一份报表时 ≈ 当天的阶段变化量。"
             "参考限度 ±15mm/天，按绝对值判定。")
    rate_col, rate_limit = rate_label, DAILY_LIMIT

    if m[rate_col].notna().any():
        if is_multi:
            # ---------- 多日：多点位速率折线（关闭图例，X 轴用类别轴） ----------
            fig = go.Figure()
            palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                       "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
            for i, (pid, g) in enumerate(sorted(m.groupby(m["测点编号"].astype(str)))):
                g = g.sort_values("日期")
                fig.add_trace(go.Scatter(
                    x=pd.to_datetime(g["日期"]).dt.strftime("%Y-%m-%d"),
                    y=g[rate_col].astype(float),
                    mode="lines+markers", name=str(pid),
                    line=dict(color=palette[i % len(palette)], width=2)))
            for y, label in ((rate_limit, "+15mm/天 警戒线"), (-rate_limit, "-15mm/天 警戒线")):
                fig.add_hline(y=y, line_dash="dash", line_color="#e03131",
                              annotation_text=label,
                              annotation_position="top left" if y > 0 else "bottom left",
                              annotation_font_color="#ff6b6b")
            peak = float(m[rate_col].astype(float).abs().max())
            span = max(rate_limit * 1.5, peak) * 1.25
            fig.update_layout(
                **DARK_PLOTLY_LAYOUT,
                hovermode="closest",
                xaxis_title="时间",
                yaxis_title=f"{rate_col}（mm/天）",
                showlegend=False,
                margin=dict(l=40, r=40, t=30, b=40),
                height=520,
            )
            # 强制类别轴：避免日期被自动展开成毫秒级刻度
            fig.update_xaxes(type="category")
            fig.update_yaxes(range=[-span, span], zeroline=True,
                             zerolinecolor="rgba(255,255,255,0.2)")
            st.plotly_chart(fig, width="stretch")
            st.caption("每条线 = 一个点位的速率变化；红色虚线 = ±15mm/天 参考警戒线（按绝对值判定）。"
                       "图例已关闭以避免遮挡：把鼠标移到线上即可看到点号与数值。")
        else:
            # ---------- 单日：横向条形图（X = 速率大小，Y = 点号） ----------
            sub = m[m[rate_col].notna()].copy()
            sub["测点编号"] = sub["测点编号"].astype(str)
            sub = sub.sort_values(rate_col, ascending=True)  # 最大值排在最上方
            vals = sub[rate_col].astype(float)
            colors = [LEVEL_COLORS[level_of_value(v, rate_limit)] for v in vals]
            fig = go.Figure(go.Bar(
                x=vals,
                y=sub["测点编号"],
                orientation="h",
                marker_color=colors,
                text=[f"{v:.1f}" for v in vals],
                textposition="outside",
            ))
            for xv, label in ((rate_limit, f"+{rate_limit:g} 警戒线"),
                              (-rate_limit, f"-{rate_limit:g} 警戒线")):
                fig.add_vline(
                    x=xv, line_dash="dash", line_color="#f2c313",
                    annotation_text=label,
                    annotation_position="top right" if xv > 0 else "bottom right",
                    annotation_font_color="#ffd54f")
            peak = float(vals.abs().max())
            span = max(rate_limit * 1.5, peak) * 1.2
            fig.update_layout(
                **DARK_PLOTLY_LAYOUT,
                xaxis_title=f"{rate_col}（mm/天）",
                yaxis_title="点号",
                showlegend=False,
                margin=dict(l=40, r=40, t=30, b=40),
                height=max(420, min(900, 26 * len(sub) + 160)),
            )
            fig.update_xaxes(range=[-span, span], zeroline=True,
                             zerolinecolor="rgba(255,255,255,0.2)")
            st.plotly_chart(fig, width="stretch")
            st.caption(f"当前只有 1 个监测日期，改用横向条形图：柱子越长速率越大，"
                       f"颜色按**绝对值**判定（≤{rate_limit:g} 绿、{rate_limit:g}~{rate_limit * 1.5:g} 黄、"
                       f">{rate_limit * 1.5:g} 红）。黄色虚线 = ±{rate_limit:g} 参考警戒线。")
    else:
        st.info("当前数据算不出速率：既没有报表自带的速率/阶段变化量列，"
                "也只有 1 个监测日期。请上传多日数据，或确认报表里包含阶段变化量列。")
