"""core/normalize.py —— 数据读取、复杂表头自动定位、列名清洗、缺失值补齐。

支持两类表格：
1. 普通单行表头（测点编号 / 日期 / 累计位移 / 沉降 …）；
2. 带大标题和双层表头的报表，例如：
   第1行：监测点变形量报表（合并单元格大标题）
   第2行：监测时间：2026-10-15
   第3行：点号 | 本次变化量       | 累计变化量
   第4行：     | ΔS(mm) | ΔH(mm) | ΔS(mm) | ΔH(mm)
   数据区『点号』合并单元格留空时自动沿用上一行；表尾备注/合计行自动剔除。
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd

# ---------------- 文本规范化：全角→半角、Δ统一成d、去空格、转小写 ----------------
_DELTA_RE = re.compile(r"[Δδ∆▽△]")
_SPACES_RE = re.compile(r"\s+")


def norm_text(v) -> str:
    """把单元格/列名洗成干净的小写字符串，用于模糊匹配。"""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    s = unicodedata.normalize("NFKC", str(v))   # 全角字母数字括号 → 半角
    s = _DELTA_RE.sub("d", s)                   # Δ/δ/∆/△/▽ → d
    s = s.replace("（", "(").replace("）", ")")
    s = _SPACES_RE.sub("", s)
    return s.lower()


# ---------------- 表头行定位 ----------------
# 出现这些字样的行才可能是表头（大标题“监测点变形量报表”不在其中）
_ANCHOR_RE = re.compile(
    r"(点号|测点编号|累计变化量|本次变化量|累计位移|累计沉降|水平位移|垂直位移"
    r"|竖向位移|沉降|位移|ds\(|dh\(|\(mm\)|监测日期|观测日期|^date)"
)
_TITLE_RE = re.compile(r"(报表|统计表|汇总表)")
_UNIT_RE = re.compile(r"(ds\(|dh\(|\(mm\)|mm$|%|沉降|位移|变化量)")
_NUM_RE = re.compile(r"-?\d+(\.\d+)?")


def _row_cells(row) -> list:
    return [c for c in row if not pd.isna(c) and str(c).strip() != ""]


def _is_header_row(row) -> bool:
    cells = _row_cells(row)
    if len(cells) < 2:
        return False                      # 合并单元格的大标题只占一格，直接跳过
    norms = [norm_text(c) for c in cells]
    if any(_TITLE_RE.search(n) for n in norms) and len(cells) <= 2:
        return False
    return any(_ANCHOR_RE.search(n) for n in norms)


def _is_unit_row(row) -> bool:
    """双层表头的第二行：整行都是 ΔS(mm)/ΔH(mm) 这类子表头，不含数字。"""
    cells = _row_cells(row)
    if not cells:
        return False
    norms = [norm_text(c) for c in cells]
    hits = sum(1 for n in norms if _UNIT_RE.search(n))
    numeric = sum(1 for n in norms if _NUM_RE.fullmatch(n))
    return hits >= 1 and numeric == 0


def _find_header_rows(grid: pd.DataFrame):
    """在前 12 行里自动找表头；返回 (首行行号, 第二层行号或 None)，找不到返回 None。"""
    n = min(12, len(grid))
    for i in range(n):
        if _is_header_row(grid.iloc[i]):
            r2 = i + 1 if (i + 1 < n and _is_unit_row(grid.iloc[i + 1])) else None
            return i, r2
    return None


_DATE_RE = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})")


def _extract_report_date(grid: pd.DataFrame, header_row: int):
    """在表头上方的行里找『监测时间：2026-10-15』这类日期，返回 date 或 None。"""
    for i in range(header_row):
        for v in grid.iloc[i]:
            s = "" if pd.isna(v) else str(v)
            if not s:
                continue
            m = _DATE_RE.search(s)
            if m:
                try:
                    return datetime(int(m.group(1)), int(m.group(2)),
                                    int(m.group(3))).date()
                except ValueError:
                    pass
    return None


def _build_columns(grid: pd.DataFrame, r1: int, r2):
    """把表头行拼成列名：双层表头拼成『累计变化量|ΔS (mm)』样式。"""
    if r2 is None:
        return [("" if pd.isna(v) else str(v).strip()) for v in grid.iloc[r1]]
    top = grid.iloc[r1].ffill()            # 横向合并单元格：向右沿用
    bot = grid.iloc[r2]
    names = []
    for a, b in zip(top, bot):
        parts = []
        for v in (a, b):
            t = "" if pd.isna(v) else str(v).strip()
            if t and t not in parts:
                parts.append(t)
        names.append("|".join(parts))
    return names


def _read_grid(file) -> pd.DataFrame:
    """按“无表头”方式读成原始网格（不解析表头），csv 自动尝试常见中文编码。"""
    name = str(getattr(file, "name", "")).lower()
    if name.endswith(".csv"):
        raw = file.read()
        last_err = None
        for enc in ("utf-8-sig", "gbk", "gb18030", "utf-8"):
            try:
                return pd.read_csv(io.BytesIO(raw), encoding=enc,
                                   header=None, dtype=object)
            except Exception as e:      # 换下一种编码再试
                last_err = e
        raise ValueError(f"CSV 文件读取失败，试了几种编码都不行：{last_err}")
    return pd.read_excel(file, header=None, dtype=object)


# ---------------- 列名匹配：双层表头按「大类 + 希腊字母」精准映射 ----------------
def _map_two_layer(col: str):
    """双层表头列（形如『累计变化量|ΔS (mm)』）精准映射为标准名，失败返回 None。"""
    if "|" not in col:
        return None
    parts = col.split("|")
    top = norm_text(parts[0])                # 大类：累计变化量 / 阶段(本次)变化量 / 速率
    sub = norm_text("|".join(parts[1:]))     # 子列：ΔS / ΔH
    is_ds = "ds" in sub or "水平" in sub     # ΔS = 水平位移方向
    is_dh = "dh" in sub or "垂直" in sub or "竖向" in sub or "沉降" in sub  # ΔH = 垂直/沉降方向
    if "速率" in top or "速度" in top:
        if is_ds or "水平" in top:
            return "水平位移速率"
        if is_dh or "垂直" in top or "竖向" in top:
            return "垂直位移速率"
    if "累计" in top:
        if is_ds:
            return "累计位移"
        if is_dh:
            return "累计沉降"
    if "阶段" in top or "本次" in top or "单次" in top:
        if is_ds:
            return "单次位移"
        if is_dh:
            return "单次沉降"
    return None


def match_columns(df: pd.DataFrame):
    """把表格里的列名改成标准名，返回 (改名后的表, 识别日志列表)。

    优先按双层表头层级精准映射（累计/阶段大类 + ΔS/ΔH）；单层表头走精准规则。
    标准名共 8 个：测点编号、日期、单次位移、单次沉降、累计位移、累计沉降、
    水平位移速率、垂直位移速率。
    """
    log, rename_map, used = [], {}, set()

    # 单层表头精准规则（顺序即优先级）
    rules = [
        ("测点编号", lambda n: "点号" in n or "测点编号" in n
            or n in ("测点", "编号", "监测点", "point", "point_id", "pointid")),
        ("日期", lambda n: "日期" in n or "监测时间" in n or "观测时间" in n
            or "采集时间" in n or n in ("时间", "date", "time")),
        ("水平位移速率", lambda n: ("速率" in n or "速度" in n)
            and ("水平" in n or "ds" in n)),
        ("垂直位移速率", lambda n: ("速率" in n or "速度" in n)
            and ("垂直" in n or "竖向" in n or "dh" in n or "沉降" in n)),
        ("单次位移", lambda n: ("单次" in n or "本次" in n or "阶段" in n)
            and ("ds" in n or "水平" in n or ("位移" in n and "沉降" not in n))),
        ("单次沉降", lambda n: ("单次" in n or "本次" in n or "阶段" in n)
            and ("dh" in n or "垂直" in n or "竖向" in n or "沉降" in n)),
        ("累计位移", lambda n: "累计" in n
            and ("ds" in n or "水平位移" in n or "位移" in n or "变形" in n)),
        ("累计沉降", lambda n: "累计" in n
            and ("dh" in n or "垂直" in n or "竖向" in n or "沉降" in n)),
        # 兼容老格式：列名里没有"累计/单次"字样
        ("累计位移", lambda n: ("位移" in n or "变形" in n)
            and "沉降" not in n and "速率" not in n),
        ("累计沉降", lambda n: "沉降" in n or "垂直位移" in n),
        # 最后兜底：孤零零的 ΔS/ΔH（按累计值处理）
        ("累计位移", lambda n: "ds" in n or "水平位移" in n),
        ("累计沉降", lambda n: "dh" in n),
    ]
    for col in df.columns:
        if not norm_text(col):
            continue
        std = _map_two_layer(str(col))          # 先走双层精准映射
        if std is not None and std not in used:
            rename_map[col] = std
            used.add(std)
            mark = "ℹ️" if ("单次" in std or "速率" in std) else "✅"
            log.append(f"{mark} 「{col}」 识别为 【{std}】（按双层表头层级+希腊字母精准映射）")
            continue
        n = norm_text(col)
        for std2, cond in rules:
            if std2 in used:
                continue
            if cond(n):
                rename_map[col] = std2
                used.add(std2)
                mark = "ℹ️" if ("单次" in std2 or "速率" in std2) else "✅"
                log.append(f"{mark} 「{col}」 识别为 【{std2}】")
                break

    for std in ("测点编号", "日期", "累计位移", "累计沉降"):
        if std not in used:
            log.append(f"❌ 没找到【{std}】对应的列")
    for c in df.columns:
        if c not in rename_map and norm_text(c):
            log.append(f"· 「{c}」未使用")
    return df.rename(columns=rename_map), log


# ---------------- 清洗补值 ----------------
_JUNK_RE = re.compile(r"合计|汇总|平均|备注|说明|最大|最小|制表|审核|监测人")


def clean(df: pd.DataFrame, fallback_date=None):
    """补缺失值 + 统一格式，返回 (清洗后的表, 补值说明列表)。"""
    df = df.copy()
    keep = [c for c in ["测点编号", "日期", "累计位移", "累计沉降",
                        "单次位移", "单次沉降", "水平位移速率", "垂直位移速率"]
            if c in df.columns]
    df = df[keep]
    notes = []

    # 0) 剔除“备注/合计”等杂行和全空行（必须在补点号之前做）
    if "测点编号" in df.columns:
        label = df["测点编号"].map(lambda v: "" if pd.isna(v) else str(v).strip())
        junk = label.str.contains(_JUNK_RE, na=False)
        data_cols = [c for c in df.columns if c != "测点编号"]
        all_blank = df[data_cols].isna().all(axis=1) if data_cols else label.eq("")
        drop_mask = junk | (all_blank & label.eq(""))
        n_junk = int(drop_mask.sum())
        if n_junk:
            df = df[~drop_mask]
            notes.append(f"剔除 {n_junk} 行备注/空行等非数据行")

    # 1) 测点编号：空着的地方沿用上一行（合并单元格、每段只写一次点号都适用）
    if "测点编号" in df.columns:
        s = df["测点编号"].astype(str).str.strip()
        mask = s.isna() | s.isin(["", "nan", "None", "NaT"])
        n_before = int(mask.sum())
        s = s.mask(mask)               # 统一变成缺失值，再向下/向上沿用
        df["测点编号"] = s.ffill().bfill().fillna("P1")
        if n_before:
            notes.append(f"测点编号补齐 {n_before} 处")
    else:
        df["测点编号"] = "P1"
        notes.append("没有点号/测点编号列，已统一记为 P1")

    # 2) 日期：优先用表里的日期列；没有就用『监测时间』行的日期或页面选的日期
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        if df["日期"].isna().all():
            df = df.drop(columns=["日期"])
    if "日期" not in df.columns:
        if fallback_date is not None:
            df["日期"] = pd.Timestamp(fallback_date)
            notes.append(f"数据里没有日期列，已统一使用日期 {pd.Timestamp(fallback_date):%Y-%m-%d}")
        else:
            raise ValueError("数据里没有日期列，也没有可用的默认日期："
                             "请在上传页选择一个日期后重新上传。")
    else:
        n_before = int(df["日期"].isna().sum())
        df["日期"] = df["日期"].ffill().bfill()
        df = df.dropna(subset=["日期"])
        if n_before:
            notes.append(f"日期补齐 {n_before} 处")

    # 3) 只有“单次（阶段）变化量”没有累计值时：按测点逐步累加出累计值
    for cum_col, cur_col in (("累计位移", "单次位移"), ("累计沉降", "单次沉降")):
        if cum_col not in df.columns and cur_col in df.columns:
            vals = pd.to_numeric(df[cur_col], errors="coerce").fillna(0)
            df[cum_col] = vals.groupby(df["测点编号"]).cumsum()
            notes.append(f"没有【{cum_col}】列，已用「{cur_col}」按测点累加得到")

    # 4) 数值列：组内线性插值，实在补不上的用中位数兜底
    for col in ["累计位移", "累计沉降", "单次位移", "单次沉降",
                "水平位移速率", "垂直位移速率"]:
        if col not in df.columns:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
        n_before = int(df[col].isna().sum())
        df[col] = df.groupby("测点编号")[col].transform(
            lambda s: s.interpolate().ffill().bfill()
        )
        med = df[col].median()
        df[col] = df[col].fillna(med if pd.notna(med) else 0)
        if n_before:
            notes.append(f"{col}补齐 {n_before} 处")

    if "累计位移" not in df.columns and "累计沉降" not in df.columns:
        raise ValueError("表里既没有累计变化量（ΔS/ΔH），也没有阶段（单次）变化量，"
                         "至少要有一样才能分析。")

    df = df.sort_values(["测点编号", "日期"]).reset_index(drop=True)
    return df, notes


def _load_one(file, fallback_date=None):
    """读取单份文件：定位表头 → 拼列名 → 规范列名 → 清洗补值。

    返回 (数据表, 识别日志, 补值说明)。
    """
    grid = _read_grid(file)
    if grid.empty:
        raise ValueError("文件是空的，没有读到任何数据。")
    hdr = _find_header_rows(grid)
    if hdr is None:
        raise ValueError("没有定位到表头行：表头里应有『点号』『ΔS/ΔH』『沉降』"
                         "『位移』等字样（大标题行请保持为合并单元格）。")
    r1, r2 = hdr
    cols = _build_columns(grid, r1, r2)
    body = grid.iloc[(r2 if r2 is not None else r1) + 1:].reset_index(drop=True)
    body.columns = cols
    renamed, log = match_columns(body)

    found = _extract_report_date(grid, r1)
    if found is not None:
        log.append(f"📅 从表头上方的『监测时间』识别到报告日期 {found:%Y-%m-%d}，"
                   f"没有日期列时将使用它")
    df, notes = clean(renamed, fallback_date=found or fallback_date)
    return df, log, notes


def load_and_clean(file, fallback_date=None):
    """单文件入口（兼容旧用法）。"""
    return _load_one(file, fallback_date)


def load_and_clean_many(files, fallback_date=None):
    """批量解析多份报表并纵向合并成总表（自动读取每个文件里的时间）。

    返回 (合并后的总表, 识别日志, 补值说明)。
    """
    frames, log, notes = [], [], []
    used = 0
    for f in files:
        fname = str(getattr(f, "name", f"文件{used + 1}"))
        try:
            df, lg, nt = _load_one(f, fallback_date)
        except Exception as e:
            log.append(f"⚠️ 文件「{fname}」解析失败，已跳过：{e}")
            continue
        used += 1
        df.insert(0, "来源文件", fname)
        frames.append(df)
        log.append(f"—— 文件「{fname}」识别结果 ——")
        log.extend(lg)
        notes.extend(f"[{fname}] {n}" for n in nt)
    if not frames:
        raise ValueError("所有文件都解析失败，请检查文件内容后重新上传。")

    total = pd.concat(frames, ignore_index=True)
    dup_cols = [c for c in ("测点编号", "日期", "累计位移", "累计沉降") if c in total.columns]
    n0 = len(total)
    total = total.drop_duplicates(subset=dup_cols, keep="first").reset_index(drop=True)
    if len(total) < n0:
        notes.append(f"自动去除跨文件重复记录 {n0 - len(total)} 条")
    n_dates = int(total["日期"].nunique())
    notes.append(
        f"合并完成：{used} 份文件、{total['测点编号'].nunique()} 个测点、{n_dates} 个监测日期"
        + ("（多日模式：将同时计算单日变化量）" if n_dates > 1 else "（单日模式：仅按累计值判定）")
    )
    return total, log, notes


def make_demo_data() -> pd.DataFrame:
    """生成一份示例数据（没有真实数据时用来跑通全流程）。"""
    rng = np.random.default_rng(7)
    dates = pd.date_range("2026-09-01", periods=30, freq="D")
    rows = []
    for pid, v0, base_speed in [("P1", 10.0, 0.30),      # 稳定：速率约0.3，绿色
                                ("P2", 12.0, 1.20),      # 黄色：速率约1.2
                                ("P3", 8.0, None)]:      # 后期加速：黄色→红色
        cum = v0
        cum_h = v0 * 0.4
        for i, d in enumerate(dates):
            if base_speed is None:
                speed = 2.5 if i < 15 else 3.0 + 0.25 * (i - 15)
            else:
                speed = base_speed
            ds = speed + rng.normal(0, 0.06)
            dh = speed * 0.4 + rng.normal(0, 0.05)
            cum += ds
            cum_h += dh
            rows.append({
                "测点编号": pid,
                "日期": d.strftime("%Y-%m-%d"),
                "累计位移": round(cum, 2),
                "累计沉降": round(cum_h, 2),
                "单次位移": round(ds, 2),
                "单次沉降": round(dh, 2),
            })
    return pd.DataFrame(rows)
