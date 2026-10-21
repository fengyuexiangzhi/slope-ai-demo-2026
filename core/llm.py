"""core/llm.py —— 调 DeepSeek API（流式输出），调不通时自动用本地缓存/规则兜底。"""
from __future__ import annotations

import json
import os
import pathlib
from datetime import datetime

from core.rules import stats_to_text

API_URL = "https://api.deepseek.com/chat/completions"
ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE_FILE = ROOT / "cache.json"
ENV_FILE = ROOT / ".env"

SYSTEM_PROMPT = "你是经验丰富的边坡工程与地质灾害防治专家，说话严谨、简练、建议可执行。"

USER_PROMPT = """以下是某边坡多测点监测数据的统计结果（双控指标预警规则：累计变化量限度 30mm，单次变化量限度 15mm；超过限度50%即累计>45mm或单次>22.5mm为红色；最终预警颜色取各指标中最严重者，变化量按绝对值判危险）：

{stats}

请严格按下面的格式输出。【研判结论】里必须作为核心结论明确写出三类信息：
1. 哪些测点【累计量超限】（最新累计变化量绝对值 >30mm）；
2. 哪些测点【单次速率超限】（单次变化量绝对值 >15mm；没有单次变化量数据时说明未涉及）；
3. 各测点的【最终预警颜色】（绿/黄/红）分布与整体判断。

【研判结论】约150字，包含上述三类核心结论，并概括变形阶段与发展趋势。
【处置建议】3条简短可执行的建议，每条以 1. 2. 3. 开头，各占一行。
不要输出格式以外的任何内容。"""


def get_api_key() -> str:
    """优先读系统环境变量，读不到再读项目文件夹里的 .env 文件。"""
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if key:
        return key
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "DEEPSEEK_API_KEY":
                    v = v.strip().strip('"').strip("'")
                    if v:
                        return v
        except Exception:
            pass
    return ""


def _api_stream(key: str, stats: dict, parts: list):
    """真正请求 DeepSeek，一行一行解析流式返回，逐段 yield 出去。"""
    import requests

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(stats=stats_to_text(stats))},
        ],
        "stream": True,
        "temperature": 0.3,
    }
    with requests.post(
        API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        stream=True,
        timeout=60,
    ) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}：{resp.text[:200]}")
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = (choices[0].get("delta") or {}).get("content") or ""
            if delta:
                parts.append(delta)
                yield delta


def _load_cache() -> str:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8")).get("text", "")
        except Exception:
            return ""
    return ""


def _save_cache(text: str):
    """AI 生成成功后存进 cache.json，以后接口调不通就用它兜底。"""
    try:
        CACHE_FILE.write_text(
            json.dumps({"updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "text": text}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def local_fallback(stats: dict) -> str:
    """没有 AI 时的本地兜底文案（格式和 AI 输出保持一致），突出三要素。"""
    pts = stats["测点明细"]
    cum_over = [p["测点编号"] for p in pts if p["累计位移超限"] or p["累计沉降超限"]]
    daily_over = [p["测点编号"] for p in pts if p["单次位移超限"] or p["单次沉降超限"]]
    reds = [p["测点编号"] for p in pts if p["最终预警"] == "红"]
    yellows = [p["测点编号"] for p in pts if p["最终预警"] == "黄"]
    greens = [p["测点编号"] for p in pts if p["最终预警"] == "绿"]

    def _names(lst):
        return "、".join(lst) if lst else "无"

    concl = (f"本次共分析{stats['测点数']}个测点、{stats['记录条数']}条数据"
             f"（{stats['日期范围'][0]}至{stats['日期范围'][1]}，{stats['数据模式']}监测）。"
             f"最终预警颜色分布：🔴红色 {_names(reds)}；🟡黄色 {_names(yellows)}；"
             f"🟢绿色 {_names(greens)}。")
    if cum_over:
        concl += f"测点{'、'.join(cum_over)}累计变化量已超过30mm限度，属累计量超限。"
    else:
        concl += "各测点累计变化量均在30mm限度以内，无累计量超限。"
    has_daily = any(p["最大单次位移"] is not None or p["最大单次沉降"] is not None
                    for p in pts)
    if has_daily:
        if daily_over:
            concl += (f"测点{'、'.join(daily_over)}单次变化量已超过15mm限度，"
                      "属单次速率超限，变形速率异常，需高度警惕。")
        else:
            concl += "各测点单次变化量均在15mm限度以内，无单次速率超限。"
    else:
        concl += "报表未提供阶段变化量（单次变化量）数据，未涉及单次速率超限判定。"
    if reds:
        concl += "存在红色预警点位，边坡整体风险较高，建议立即启动应急响应。"
    elif yellows:
        concl += "暂无红色预警，但黄色点位变形已超限，需持续关注发展趋势。"
    else:
        concl += "所有点位均为绿色预警，边坡整体处于稳定状态。"

    if reds:
        a1 = "1. 对红色测点立即加密监测至每日1次并加装自动化设备实时盯守，必要时组织卸载或支护加固；"
    elif yellows:
        a1 = "1. 对黄色测点加密监测至每日1次，重点核查其累计量与单次变化量的变化趋势；"
    else:
        a1 = "1. 维持现有监测频率，每周复核一次数据与双控阈值；"
    advice = [
        a1,
        "2. 排查坡面裂缝、排水沟和坡脚冲刷情况，及时封堵裂缝、疏通排水；",
        "3. 在红色/黄色测点影响范围设置警戒区，强降雨期间禁止人员进入，发现异常立即上报并启动预案。",
    ]
    return "【研判结论】" + concl + "\n【处置建议】\n" + "\n".join(advice)


def generate(stats: dict):
    """主入口：返回 (流式生成器, status字典)。

    status['source'] 只有三种：'ai'（DeepSeek实时生成）、'cache'（本地缓存）、'local'（本地规则兜底）。
    """
    status = {"source": "local", "error": None}
    return _stream(stats, status), status


def _stream(stats: dict, status: dict):
    parts: list = []
    key = get_api_key()
    if key:
        try:
            status["source"] = "ai"
            got = False
            for chunk in _api_stream(key, stats, parts):
                got = True
                yield chunk
            if got:
                _save_cache("".join(parts))   # 成功才写缓存
                return
        except Exception as e:
            status["error"] = str(e)
            yield f"\n\n> ⚠️ AI 接口调用失败（{e}），已自动切换本地兜底。\n\n"

    cached = _load_cache()
    if cached:
        status["source"] = "cache"
        yield cached
        return
    status["source"] = "local"
    yield local_fallback(stats)
