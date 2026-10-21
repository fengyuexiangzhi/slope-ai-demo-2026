"""全局深色科技风主题 + 侧边栏品牌/页脚。所有页面在 set_page_config 后调用 apply_theme()。"""
import streamlit as st

# 统一复用的 Plotly 深色透明布局（paper/plot 透明、文字浅灰、网格淡化）
DARK_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#cfd8dc", family="Segoe UI, Microsoft YaHei, sans-serif"),
    xaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.15)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.15)"),
    # 注意：这里不放 legend，避免与各图 update_layout 里的 legend= 参数重复导致 TypeError
)
# 图例通用深色样式（需要图例的图自行合并：legend={**LEGEND_STYLE, ...})
LEGEND_STYLE = dict(
    bgcolor="rgba(0,0,0,0)",
    bordercolor="rgba(255,255,255,0.1)",
    font=dict(color="#cfd8dc"),
)

# 全局深色 CSS（只注入一次，靠 session_state 标记避免重复）
_GLOBAL_CSS = """
<style>
/* ========== 基础：强制深色背景 + 浅色文字 ========== */
html, body, #root,
.stApp, .stApp > header, .main,
[data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stToolbar"], [data-testid="stDecoration"],
section[data-testid="stSidebar"] {
    background-color: #0a0e1a !important;
    background-image: none !important;
}
.stApp {
    color: #e0e6ed !important;
}
body, p, span, div, label, .stMarkdown, .stCaption, .stText {
    color: #e0e6ed !important;
}
/* 副文本（caption）略灰 */
.stCaption, .stCaption * { color: #8a96a6 !important; }

/* ========== 顶部白边彻底去掉：隐藏 header + 顶部装饰条 + 归零留白 ========== */
[data-testid="stHeader"], header[data-testid="stHeader"], .stApp > header {
    background: transparent !important;
    background-color: transparent !important;
    box-shadow: none !important;
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
}
/* Streamlit 顶部彩色装饰细条 */
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"] { background: transparent !important; }
[data-testid="stAppViewContainer"] > .main,
[data-testid="stAppViewContainer"] > section.main {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
/* 折叠侧边栏后左上角的展开按钮：贴回顶部，避免留白 */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"] {
    top: 0.35rem !important;
    color: #00d4aa !important;
}

/* ========== 全宽：去掉 Streamlit 默认窄屏限制 ========== */
.block-container {
    max-width: 95% !important;
    padding-top: 0.4rem !important;
    margin-top: 0 !important;
    padding-bottom: 2rem !important;
}

/* ========== 侧边栏 ========== */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1424 0%, #0a0e1a 100%) !important;
    border-right: 1px solid rgba(0, 212, 170, 0.18) !important;
}
/* 侧边栏顶部品牌（用 ::before 插入到导航上方） */
section[data-testid="stSidebar"] > div:first-child::before {
    content: "⛰️  边坡智测 · AI 动态研判平台";
    display: block;
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-align: center;
    padding: 1.1rem 0.8rem 0.9rem 0.8rem;
    margin: 0 -1rem 0.8rem -1rem;
    background: linear-gradient(135deg, rgba(0,179,134,0.20), rgba(0,120,200,0.12));
    border-bottom: 1px solid rgba(0, 212, 170, 0.28);
    background-clip: padding-box;
    color: #00d4aa;
    text-shadow: 0 0 12px rgba(0,212,170,0.45);
    line-height: 1.35;
}
section[data-testid="stSidebar"] > div:first-child::after {
    content: "SLOPE AI MONITORING";
    display: block;
    text-align: center;
    font-size: 0.66rem;
    letter-spacing: 3px;
    color: #5a6675;
    margin: -0.5rem 0 1rem 0;
}

/* ========== 侧边栏导航：自动多页导航 stSidebarNav + st.page_link ========== */
[data-testid="stSidebarNav"] { padding-top: 0.2rem !important; }
[data-testid="stSidebarNav"] ul { gap: 2px !important; }
[data-testid="stSidebarNav"] a,
[data-testid="stSidebarNavLink"],
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
    font-size: 1.0rem !important;
    padding: 0.55rem 0.75rem !important;
    border-radius: 8px !important;
    margin: 2px 0.45rem !important;
    transition: all 0.28s ease !important;
    color: #c5ced9 !important;
    border-left: 3px solid transparent !important;
    background-color: transparent !important;
}
/* 悬浮：半透明青色 + 右移 */
[data-testid="stSidebarNav"] a:hover,
[data-testid="stSidebarNavLink"]:hover,
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
    background-color: rgba(0, 212, 170, 0.12) !important;
    color: #ffffff !important;
    transform: translateX(3px);
}
/* 选中：科技感深蓝/半透明蓝底 + 亮绿文字 + 青色发光边 */
[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
    background: linear-gradient(90deg, rgba(0, 74, 173, 0.85) 0%, rgba(0, 140, 255, 0.38) 100%) !important;
    color: #7dffc4 !important;
    font-weight: 700 !important;
    border-left: 3px solid #00ffb3 !important;
    box-shadow: inset 0 0 0 1px rgba(79, 195, 247, 0.45),
                0 2px 14px rgba(0, 120, 255, 0.35) !important;
}
/* 导航内的图标/文字颜色统一跟随父级（覆盖全局 span 浅色） */
[data-testid="stSidebarNav"] a span,
[data-testid="stSidebarNav"] a p,
[data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNavLink"] p,
[data-testid="stSidebarNavLink"] svg,
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] span,
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p {
    color: inherit !important;
    fill: currentColor !important;
}

/* 侧边栏底部版本信息 */
.sidebar-footer {
    margin-top: 1.5rem;
    padding-top: 0.8rem;
    border-top: 1px solid rgba(0, 212, 170, 0.18);
    text-align: center;
    font-size: 0.72rem;
    color: #6b7785 !important;
    line-height: 1.6;
}
.sidebar-footer .ver { color: #00d4aa !important; font-weight: 600; }
.sidebar-footer .powered { color: #8a96a6 !important; }

/* ========== 页面大标题：底色 + 阴影 ========== */
h1, .stHeading h1 {
    background: linear-gradient(90deg, rgba(0,179,134,0.22), rgba(0,120,200,0.10)) !important;
    padding: 0.7rem 1.1rem !important;
    border-radius: 10px !important;
    border-left: 4px solid #00d4aa !important;
    box-shadow: 0 4px 18px rgba(0,0,0,0.45) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px;
}
h2, h3, .stHeading h2, .stHeading h3 {
    color: #e0e6ed !important;
    border-bottom: 1px solid rgba(0,212,170,0.15);
    padding-bottom: 0.3rem;
}

/* ========== 卡片/容器毛玻璃 ========== */
[data-testid="stMetric"] {
    background: rgba(15, 20, 36, 0.7) !important;
    border: 1px solid rgba(0, 212, 170, 0.18) !important;
    border-radius: 10px !important;
    padding: 0.8rem 1rem !important;
}

/* ========== 按钮 ========== */
.stButton > button {
    background: linear-gradient(135deg, #00695c, #00838f) !important;
    color: #fff !important;
    border: 1px solid rgba(0,212,170,0.4) !important;
    border-radius: 8px !important;
    transition: all 0.25s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #00897b, #00acc1) !important;
    box-shadow: 0 0 14px rgba(0,212,170,0.5) !important;
    transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00b386, #00838f) !important;
}

/* ========== Tabs ========== */
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
    background-color: rgba(15,20,36,0.6) !important;
    color: #c5ced9 !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s ease;
}
.stTabs [data-baseweb="tab"]:hover { background-color: rgba(0,212,170,0.12) !important; color: #fff !important; }
.stTabs [aria-selected="true"] {
    background: linear-gradient(180deg, rgba(0,179,134,0.35), rgba(0,179,134,0.1)) !important;
    color: #fff !important;
    border-bottom: 2px solid #00d4aa !important;
}

/* ========== 表格：深色表头 + 斑马纹 ========== */
[data-testid="stDataFrame"] table thead th {
    background-color: #141c2c !important;
    color: #00d4aa !important;
    font-weight: 600 !important;
    border-bottom: 2px solid rgba(0,212,170,0.3) !important;
}
[data-testid="stDataFrame"] table tbody tr:nth-child(even) {
    background-color: rgba(20, 28, 44, 0.5) !important;
}
[data-testid="stDataFrame"] table tbody tr:nth-child(odd) {
    background-color: rgba(10, 14, 26, 0.5) !important;
}
[data-testid="stDataFrame"] table tbody td {
    color: #d0d7de !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
}
/* 红色预警文字加粗标红：由页面 3 的 pandas Styler 内联实现，
   此处保留表头深色 + 斑马纹的全局样式即可 */

/* ========== Expander / Selectbox / 输入框 ========== */
[data-testid="stExpander"] {
    background: rgba(15,20,36,0.5) !important;
    border: 1px solid rgba(0,212,170,0.15) !important;
    border-radius: 10px !important;
}
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div,
.stDateInput input {
    background-color: #0f1424 !important;
    color: #e0e6ed !important;
    border-color: rgba(0,212,170,0.2) !important;
}
.stSelectbox label, .stDateInput label, .stTextInput label, .stFileUploader label {
    color: #c5ced9 !important;
}

/* ========== 警告/信息框配色 ========== */
[data-testid="stAlert"] {
    background: rgba(15,20,36,0.6) !important;
    border-left: 4px solid #00d4aa !important;
    color: #e0e6ed !important;
}
[data-testid="stAlert"][data-testid*="warning"] { border-left-color: #f2c313 !important; }
[data-testid="stAlert"][data-testid*="error"] { border-left-color: #e03131 !important; }
[data-testid="stAlert"][data-testid*="success"] { border-left-color: #2fb344 !important; }

/* ========== 代码块 ========== */
code, pre {
    background-color: #0f1424 !important;
    color: #b0bec5 !important;
    border: 1px solid rgba(0,212,170,0.12) !important;
    border-radius: 6px !important;
}

/* ========== 分割线 ========== */
hr, [data-testid="stDivider"] {
    border-color: rgba(0,212,170,0.15) !important;
}

/* ========== 文件上传器 ========== */
[data-testid="stFileUploader"] {
    background-color: rgba(15,20,36,0.5) !important;
    border: 1px dashed rgba(0,212,170,0.3) !important;
    border-radius: 10px !important;
}
[data-testid="stFileUploader"] section {
    background-color: transparent !important;
}

/* ========== Spinner ========== */
[data-testid="stSpinner"] { color: #00d4aa !important; }

/* ========== 链接 ========== */
a { color: #4fc3f7 !important; }
a:hover { color: #00d4aa !important; }

/* ========== 滚动条 ========== */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #0a0e1a; }
::-webkit-scrollbar-thumb { background: rgba(0,212,170,0.3); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,212,170,0.5); }

/* ========== 移动端适配 ========== */
@media (max-width: 768px) {
    .block-container { max-width: 100% !important; padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
    .sidebar-brand .brand-name { font-size: 1rem; }
}
</style>
"""


def apply_theme():
    """注入全局深色科技风 CSS + 侧边栏品牌与版本页脚。每个页面在 set_page_config 后调用一次。"""
    if not st.session_state.get("_theme_injected"):
        st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)
        st.session_state["_theme_injected"] = True

    # 侧边栏顶部品牌由 CSS ::before 注入（见 _GLOBAL_CSS），此处只加底部分割线 + 版本信息
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-footer">'
            '<span class="ver">V1.0 工程演示版</span><br>'
            '<span class="powered">Powered by Trae AI</span>'
            '</div>',
            unsafe_allow_html=True,
        )
