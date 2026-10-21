"""④ 智能研判页"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import streamlit as st

from core import llm
from core.rules import summarize, stats_to_text
from core.style import apply_theme

st.set_page_config(page_title="④ 智能研判", page_icon="🤖", layout="wide")
apply_theme()
st.title("🤖 第 4 步：AI 智能研判")
st.caption("把统计结果发给 DeepSeek，输出约 120 字研判结论 + 3 条处置建议（流式打字效果）。")

if st.session_state.get("metrics") is None:
    st.warning("还没有计算结果，请先到左侧「② 趋势计算」点一下。")
    st.stop()

m = st.session_state.metrics
stats = summarize(m)

with st.expander("📤 将发给 AI 的统计摘要（点开可查看）"):
    st.code(stats_to_text(stats), language="text")

if llm.get_api_key():
    st.success("✅ 已检测到 DeepSeek API Key，可以正常使用 AI 研判。")
else:
    st.warning(
        "⚠️ 没检测到 API Key：请在项目文件夹的 `.env` 文件里填 `DEEPSEEK_API_KEY=你的Key` 后保存。"
        "没 Key 也能点下面的按钮，会走本地缓存/规则兜底。"
    )

if st.button("🚀 开始 AI 研判", type="primary"):
    stream, status = llm.generate(stats)
    with st.spinner("AI 正在分析，请稍候……"):
        text = st.write_stream(stream)
    st.session_state.ai_result = {"text": text, "source": status["source"]}
    src = {
        "ai": "✅ 来源：DeepSeek 实时生成（已自动存入 cache.json，下次断网也能用）",
        "cache": "📁 来源：本地 cache.json 缓存",
        "local": "📋 来源：本地规则兜底（未配置 API 或调用失败时自动启用）",
    }.get(status["source"], "")
    if src:
        st.caption(src)
elif st.session_state.get("ai_result"):
    st.markdown(st.session_state.ai_result["text"])
    src = {
        "ai": "✅ 来源：DeepSeek 实时生成",
        "cache": "📁 来源：本地 cache.json 缓存",
        "local": "📋 来源：本地规则兜底",
    }.get(st.session_state.ai_result.get("source", ""), "")
    if src:
        st.caption(src)
else:
    st.info("点上面的「🚀 开始 AI 研判」按钮开始分析。")
