"""边坡监测 AI 分析平台 —— 主入口。运行方式：streamlit run app.py"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import streamlit as st

from core.style import apply_theme

st.set_page_config(page_title="边坡智测 · AI 动态研判平台", page_icon="⛰️", layout="wide")
apply_theme()

st.title("⛰️ 边坡智测 · AI 动态研判平台")
st.caption("使用流程：① 数据上传 → ② 趋势计算 → ③ 图形生成 → ④ 智能研判 → ⑤ 报告生成（全部在左侧菜单点击）")

# 初始化跨页面共享的数据
if "df" not in st.session_state:
    st.session_state.df = None
if "metrics" not in st.session_state:
    st.session_state.metrics = None
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None

# 当前进度一览
steps = [
    ("① 数据上传", st.session_state.df is not None),
    ("② 趋势计算", st.session_state.metrics is not None),
    ("③ 图形生成", st.session_state.metrics is not None),
    ("④ 智能研判", st.session_state.ai_result is not None),
    ("⑤ 报告生成", st.session_state.metrics is not None),
]
cols = st.columns(5)
for c, (name, ok) in zip(cols, steps):
    c.markdown(
        f"**{name}**<br><span style='color:{'#2fb344' if ok else '#999'}'>"
        f"{'✅ 已完成' if ok else '⬜ 未完成'}</span>",
        unsafe_allow_html=True,
    )

# 数据状态
st.divider()
st.subheader("当前数据状态")
df = st.session_state.df
if df is None:
    st.info("还没有上传数据。请点击左侧「① 数据上传」上传 xlsx/csv，或用页面上的按钮生成示例数据。")
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("记录条数", len(df))
    c2.metric("测点数量", df["测点编号"].nunique())
    c3.metric("日期范围", f"{df['日期'].min():%Y-%m-%d} ~ {df['日期'].max():%Y-%m-%d}")

with st.expander("❓ 第一次用？先看这三句话"):
    st.markdown(
        "1. **准备一个 Excel 表**：表头里要有「测点编号、日期、累计位移、沉降」这几列"
        "（叫别的名字也没关系，程序会自动认，缺了的自动补）。\n"
        "2. **按左边菜单从上往下点**：先传数据，再算趋势、看图，最后让 AI 研判、生成 Word 报告。\n"
        "3. **AI 功能需要 DeepSeek 的 Key**：在项目文件夹的 `.env` 文件里填上就能用；"
        "不填也能跑，只是研判会走本地兜底。"
    )
