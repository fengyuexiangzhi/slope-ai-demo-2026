"""① 数据上传页（支持批量上传多份 Excel，自动合并成总表）"""
import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from core.normalize import load_and_clean_many, make_demo_data
from core.style import apply_theme

st.set_page_config(page_title="① 数据上传", page_icon="📤", layout="wide")
apply_theme()
st.title("📤 第 1 步：数据上传")
st.caption("支持一次选中**多份** Excel（按住 Ctrl 逐个点选）：系统自动读取每个文件里的监测时间，"
           "纵向合并成总表。只有单日数据也能用（只算累计值）；多日数据会同时计算单日变化量（日速率）。")

if "df" not in st.session_state:
    st.session_state.df = None
if "metrics" not in st.session_state:
    st.session_state.metrics = None
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

uploaded = st.file_uploader(
    "把文件拖到这里，或点击选择文件（可按住 Ctrl 多选）",
    type=["xlsx", "csv"],
    accept_multiple_files=True,
)

fallback_date = st.date_input(
    "文件里没有日期时用的兜底日期（默认今天）",
    value=date.today(),
    help="像『监测点变形量报表』这类整表只有一天的数据："
         "如果表头上方能识别到『监测时间：xxxx-xx-xx』就优先用它，"
         "否则用这里选的日期填给该文件的所有数据行。",
)

if uploaded:
    try:
        with st.spinner(f"正在读取和合并 {len(uploaded)} 份文件……"):
            df, log, notes = load_and_clean_many(uploaded, fallback_date=fallback_date)
        n_dates = int(df["日期"].nunique())
        if n_dates > 1:
            st.success(
                f"读取成功！{len(uploaded)} 份文件已合并为 {len(df)} 行，"
                f"识别到 {n_dates} 个监测日期（{df['日期'].min():%Y-%m-%d} 至 {df['日期'].max():%Y-%m-%d}）。"
                f"**多日模式**：后面会同时计算单日变化量（日速率）。"
            )
        else:
            st.success(
                f"读取成功！共 {len(df)} 行数据，只有 1 个监测日期。"
                f"**单日模式**：只按累计值判定预警。"
            )

        with st.expander(f"📋 列名识别日志（{len(log)} 条，点开看）"):
            for line in log:
                st.write(line)

        if notes:
            st.info("自动处理情况：" + "；".join(notes))

        st.subheader("合并后的数据预览（前 20 行）")
        st.dataframe(df.head(20), width="stretch", hide_index=True)

        # 存到全局，后面几页都要用；新数据要清空旧的计算结果
        st.session_state.df = df
        st.session_state.metrics = None
        st.session_state.ai_result = None

        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下载合并后的数据 (csv)", csv, "合并后数据.csv", "text/csv")
    except Exception as e:
        st.error(f"读取失败：{e}")
        st.session_state.df = None
else:
    st.divider()
    st.markdown("**还没有数据？** 点下面按钮生成一份示例数据，先把全流程跑通：")
    if st.button("🧪 生成示例数据（3 个测点 × 30 天）"):
        df = make_demo_data()
        st.session_state.df = df
        st.session_state.metrics = None
        st.session_state.ai_result = None
        st.success("示例数据已生成！点左侧「② 趋势计算」继续。")

    with st.expander("📋 支持的数据格式（点开看）"):
        st.markdown(
            "**格式一：普通表格**（一行表头）——长这样就行，列的顺序随意、名字换成常见别名也认得：\n\n"
            "| 测点编号 | 日期 | 累计位移 | 累计沉降 |\n|---|---|---|---|\n"
            "| P1 | 2026-09-01 | 10.2 | 4.1 |\n"
            "| P2 | 2026-09-01 | 12.0 | 4.8 |"
        )
        st.markdown(
            "**格式二：带大标题和双层表头的报表**——也支持，例如：\n\n"
            "- 第1行：监测点变形量报表（大标题，合并单元格）\n"
            "- 第2行：监测时间：2026-10-15\n"
            "- 第3~4行：点号 + 「本次/累计变化量」下的 ΔS (mm)、ΔH (mm)\n\n"
            "程序会自动跳过大标题、定位双层表头，并按「大类 + 希腊字母」精准映射："
            "「累计变化量」下的 ΔS→累计位移、ΔH→累计沉降；「阶段/本次变化量」下的 "
            "ΔS→单次位移、ΔH→单次沉降；「水平/垂直位移速率」列直接提取；"
            "点号合并单元格自动向下补齐，表尾备注/合计行自动剔除；整表没有日期列时用上面选的日期。"
        )
        st.markdown(
            "**批量上传多份文件**：每份报表只放一天的监测数据（报表里写清楚监测时间），"
            "多选一次传上来，系统会按时间自动合并。同一份文件传两遍会自动去重，不用担心。"
        )
