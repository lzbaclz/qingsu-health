"""LLM 适配层。

边界（来自立项书第六节）：模型只负责
  1. 从口语中抽取协议定义的事实（带原话引用）；
  2. 只根据已有事实生成一小段叙述。
模型**不**决定问什么、不触发红旗、不给诊断/用药、不改事实状态；它的输出在 extraction/service.py
里被当作"候选"，经程序校验（key 存在、引文逐字在原文、取值合法）后才写入事实库。

提供者（TIJI_LLM_PROVIDER）：
  - mock：确定性、离线，用协议词表做抽取；用于演示兜底、测试、评测基线。
  - anthropic：官方 SDK（beta.messages.parse + Pydantic 结构化输出），默认 claude-opus-5，
    开启服务端拒答回退（fallbacks="default"）、system 提示缓存、可配置 effort。
  - compat：OpenAI 兼容的 /chat/completions（DeepSeek、通义千问 DashScope 兼容模式、智谱等国产模型），
    JSON 模式 + Pydantic 校验 + 一次纠错重试。境内真实患者数据应使用已备案的境内模型或私有化部署。
真实模型调用失败时（网络、超时、拒答、格式错误、缺 key、SDK 参数不被接受——任何异常），TIJI_LLM_FALLBACK=mock
会退回离线词表并在结果里标注 provider="mock(fallback)"，最近一次错误在 /api/health 与医生端顶栏可见；
评测时设为 none，让失败如实暴露。连通性自检：`make llm-check`（python -m app.llm.check），见 probe()。
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Literal, Optional, Protocol as TypingProtocol

from pydantic import BaseModel, Field, ValidationError

from ..config import settings
from ..protocol.schema import Protocol

log = logging.getLogger("tiji.llm")


class CandidateFact(BaseModel):
    key: str = Field(description="协议中的 fact key")
    status: Literal["present", "denied", "uncertain"]
    value: Optional[str | list[str] | float | bool] = Field(default=None, description="enum 用 option.value；多选用列表；数值用数字；是否题用 true")
    quote: str = Field(description="患者原话中支持该判断的逐字片段（必须是原文的连续子串）")
    subject: Optional[Literal["patient", "other", "unclear"]] = Field(default=None, description="事实说的是患者本人、其他人或不清楚")
    time_relation: Optional[Literal["new", "ongoing", "historical", "worsening", "improving", "past", "unknown"]] = Field(default=None, description="新发、延续、历史提及但当前未知、加重、减轻、过去已结束、起病关系未知")
    time_text: str = Field(default="", description="逐字时间线索；没有就留空，不把录入日期当起病日期")
    context_quote: str = Field(default="", description="包含症状、主体与时间线索的原文连续片段，不能拼接")


class ExtractionOutput(BaseModel):
    facts: list[CandidateFact] = Field(default_factory=list)
    unmapped_mentions: list[str] = Field(default_factory=list, description="患者提到但协议里没有对应事实的内容，原话片段")


class ProviderError(RuntimeError):
    """真实模型调用失败（网络、超时、拒答、输出格式不合法）。"""


class LLMProvider(TypingProtocol):
    name: str

    def extract(self, text: str, protocol: Protocol) -> ExtractionOutput: ...

    def narrative(self, fact_lines: list[str], protocol: Protocol) -> str: ...

    def patient_explain(self, doctor_notes: str, protocol: Protocol) -> str: ...


# ---------------------------------------------------------------- 用量统计（评测报告与 BP 成本估算用）
class _Usage:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self.calls = 0
            self.errors = 0
            self.fallbacks = 0
            self.input_tokens = 0
            self.output_tokens = 0
            self.cache_read_tokens = 0
            self.cache_write_tokens = 0
            self.latencies: dict[str, list[float]] = {"extract": [], "narrative": []}

    def add(self, kind: str, seconds: float, inp: int = 0, out: int = 0, cache_read: int = 0, cache_write: int = 0) -> None:
        with self._lock:
            self.calls += 1
            self.input_tokens += inp
            self.output_tokens += out
            self.cache_read_tokens += cache_read
            self.cache_write_tokens += cache_write
            self.latencies.setdefault(kind, []).append(seconds)

    def snapshot(self) -> dict:
        def pct(xs: list[float], q: float) -> float | None:
            if not xs:
                return None
            xs = sorted(xs)
            return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2)

        return {"calls": self.calls, "errors": self.errors, "fallbacks": self.fallbacks,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cache_read_tokens": self.cache_read_tokens, "cache_write_tokens": self.cache_write_tokens,
                "latency_s": {k: {"n": len(v), "p50": pct(v, 0.5), "p90": pct(v, 0.9)} for k, v in self.latencies.items()}}


USAGE = _Usage()


# ---------------------------------------------------------------- 真实模型共用的提示词
EXTRACTION_RULES = """你是门诊就诊前的信息整理助手。你只做一件事：把患者的一段口语描述，映射到给定的"事实清单"。
你不做诊断、不推测病因、不给任何建议。

硬性规则：
1. 只能使用清单里的 key；清单里没有对应事实的内容，放进 unmapped_mentions（原话片段）。
2. 每条事实必须给 quote：患者原话中逐字出现的一段连续文字，不得改写、不得拼接多处。
3. status：present = 患者明确表示有，或给出了具体取值；denied = 患者明确否认；
   uncertain = 患者自己表达不确定（好像、说不好、可能、不确定之类）。
   患者没提到的事实一律不要输出——"没提到"不等于"没有"。
4. 看清时间范围：说的是以前 / 既往 / 反复发作，还是这一次；"这一次开始多久"只根据描述本次发作的话来判断，
   既往病史不能当作本次起病时间。没有发生的事（差一点、险些）不算发生过；很久以前的事不算"近期"。
5. 否定只作用于它修饰的那部分；"以前没有、现在有"记为现在有。
6. 左右以患者自己的身体为准。部位和感觉要分开判断：某处麻木，要看麻的是哪里，不要把一个部位的感觉套到另一个部位。
7. 取值：单选 / 多选只能用清单给出的 value；身体区域用清单给出的区域 id；量表 / 数值用数字；是否题用 true。
   口语与清单措辞不同没关系，按意思映射；拿不准该记"有"还是"不确定"时，记 uncertain。
8. 原话可能来自语音输入：可能没有标点、有同音错字或口头禅，也可能是方言说法；按意思理解，但 quote 仍须逐字照抄原文。
"""

# 红旗专查（第 1 轮团队评审 · 计算机）：主抽取之后，只针对红旗事实再查一遍，结果与主抽取合并时取更警惕的一边
RED_FLAG_FOCUS = """这一遍只看需要尽快让医生知道的情况（下面清单里的事实）。
患者可能用方言、比喻、委婉或含糊的说法（例如用身体感觉来描述，而不说医学名称），意思相符就记录；
明确否认的记 denied；拿不准、说得含糊的记 uncertain；没提到的一律不要输出。
"""

PATIENT_REWRITE_RULES = """你帮门诊医生把他写的要点改写成患者看得懂的中文说明。医生会核对后再发送，内容由医生负责。
硬性规则：
1. 只能改写医生要点里已有的内容。不得增加、删除或改变任何医学内容：诊断、检查、药名、剂量、次数、活动建议、时间安排都必须与要点一致。
2. 要点里没有出现的病名和药名，一律不得出现；要点里写了的，照原样保留，不要换成别的说法。
3. 用短句和"你"称呼患者；专业词后面用括号加一句大白话解释；拿不准怎么改写时，照抄医生原句。
4. 只输出改写后的说明正文，分条写，不要称呼、不要落款；复诊时间和紧急情况提示由系统另外附上，你不要写。"""

NARRATIVE_RULES = """你把下面这份已经结构化的患者表达整理成 2–3 句中文叙述，供医生快速阅读。
硬性规则：只能复述列表中出现的信息；不得补充、推断、给出诊断、病名、检查或治疗建议，不得出现任何药名；
列表里写"未明确"的项目要写成"未明确"，不能写成"没有"。"""


def fact_catalog(protocol: Protocol) -> str:
    """事实清单：key [类型] 名称 · 可选值 value(名称：口语示例) · 口语示例（有 / 没有）。示例来自协议词表。"""
    lines = []
    for f in protocol.facts:
        line = f"- {f.key} [{f.type}] {f.label}"
        if f.options:
            opts = []
            for o in f.options:
                syn = "/".join(o.synonyms[:4])
                opts.append(f"{o.value}({o.label}{'：' + syn if syn else ''})")
            line += " · 可选值：" + "，".join(opts)
        if f.lexicon and (f.lexicon.present_terms or f.lexicon.denied_terms):
            ex = []
            if f.lexicon.present_terms:
                ex.append("有：" + "/".join(f.lexicon.present_terms[:5]))
            if f.lexicon.denied_terms:
                ex.append("没有：" + "/".join(f.lexicon.denied_terms[:4]))
            line += " · 口语示例（" + "；".join(ex) + "）"
        if f.min is not None or f.max is not None:
            line += f" · 范围 {f.min}–{f.max}"
        lines.append(line)
    return "\n".join(lines)


def extraction_system_prompt(protocol: Protocol) -> str:
    context = ("\n事件核实：为候选给出 subject、time_relation、time_text、context_quote。"
               "不要丢弃明确属于他人或过去已结束的症状，保留候选并如实标记；程序会区分患者当前事实。"
               "subject=patient 只指当前就诊者；我妈/家人不是患者，但‘我妈说我…’仍可能是患者。"
               "time_relation 的 new 必须有新发证据，ongoing 表示过去起始且仍存在，past 表示过去已结束。"
               "‘这次才提到’不等于 new。只说现在有而没说明起始，记 unknown；不同部位或事件不要强行合并。"
               "time_text 与 context_quote 必须逐字来自原文，拿不准主体或时间就用 unclear/unknown。") if protocol.event_verification.enabled else ""
    return EXTRACTION_RULES + context + "\n事实清单：\n" + fact_catalog(protocol)


def red_flag_keys_for_pass(protocol: Protocol) -> list[str]:
    """红旗专查的事实：红旗筛查类是否型事实，加上腿没劲（多条红旗规则的前提）。"""
    keys = protocol.red_flag_screen_keys | ({"leg_weakness"} & set(protocol.fact_index))
    return [f.key for f in protocol.facts if f.key in keys]


def red_flag_system_prompt(protocol: Protocol) -> str:
    keys = set(red_flag_keys_for_pass(protocol))
    sub = protocol.model_copy(update={"facts": [f for f in protocol.facts if f.key in keys]})
    return extraction_system_prompt(sub) + "\n" + RED_FLAG_FOCUS


# ---------------------------------------------------------------- mock
# 只收"拿不准"类措辞；"有点 / 有一点"是程度（"有点憋不住"= 有），"偶尔"是频率，都不算不确定
_HEDGES = ("好像", "似乎", "可能", "不太确定", "说不清", "说不好", "说不上来", "拿不准", "大概", "不知道是不是")
_GENERIC_LABELS = {"是", "否", "有", "没有", "不确定", "不适用", "都没有", "不清楚", "两者都有"}
# 否定词与被否定的词之间允许隔 0–2 个字（"没有腿麻""不怎么麻"），但不跨标点
_NEG = r"(没有|没|无|不|未|从没|从未)[^，,。；;！!？?\s]{0,2}\s*"
_QUESTION_FORMS = re.compile(r"是不是|有没有|会不会|能不能|要不要|说不好|说不清|说不上来|拿不准|不知道是不是")
_SPLIT = re.compile(r"[。！？；;!?\n，,、]+")  # 按短句切分：模糊词/否定词只作用于所在短句


class MockProvider:
    def structured_task(self, kind: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        raise ProviderError("离线词表不执行通用语义判断")
    """基于协议词表的确定性抽取器。目的：离线可跑、结果可复现、给评测一个诚实的基线。"""
    name = "mock"

    def extract(self, text: str, protocol: Protocol) -> ExtractionOutput:
        out = ExtractionOutput()
        clauses = [c.strip() for c in _SPLIT.split(text) if c.strip()]
        seen: set[tuple[str, str]] = set()
        for clause in clauses:
            hedged = any(h in clause for h in _HEDGES)
            # "是不是 / 有没有 / 说不好"这类是疑问或拿不准的句式，不是否定；判断否定前先去掉
            neg_clause = _QUESTION_FORMS.sub(" ", clause)
            for f in protocol.facts:
                if f.lexicon and f.lexicon.context_terms and not any(t in clause for t in f.lexicon.context_terms):
                    continue
                # 1) 枚举/多选：按 option 同义词命中（长词优先，命中后遮盖，避免"左边腰"同时命中"腰"）
                if f.options:
                    work = clause
                    # 显式 synonyms 由协议作者负责（可以是单字如"酸"）；label 自动参与匹配，但单字/通用标签（是/否/不确定）除外
                    pairs = [(o.value, syn) for o in f.options for syn in o.synonyms if syn]
                    pairs += [(o.value, o.label) for o in f.options if len(o.label) >= 2 and o.label not in _GENERIC_LABELS]
                    pairs.sort(key=lambda t: -len(t[1]))
                    hits: list[str] = []
                    denied_hits: list[str] = []
                    for val, syn in pairs:
                        if syn in work:
                            if re.search(_NEG + re.escape(syn), _QUESTION_FORMS.sub(" ", work)):
                                denied_hits.append(val)
                            else:
                                hits.append(val)
                            work = work.replace(syn, " " * len(syn))
                    if hits:
                        status = "uncertain" if hedged else "present"
                        if f.type in ("multi_enum", "body_regions"):
                            value: str | list[str] = sorted(set(hits))
                            sig = (f.key, str(value))
                            if sig not in seen:
                                seen.add(sig)
                                out.facts.append(CandidateFact(key=f.key, status=status, value=value, quote=clause))
                        else:
                            for h in dict.fromkeys(hits):
                                sig = (f.key, h)
                                if sig not in seen:
                                    seen.add(sig)
                                    out.facts.append(CandidateFact(key=f.key, status=status, value=h, quote=clause))
                    # 注意：否定某个选项（"没有摔倒"）不等于否认整个事实（诱因），因此不产生 denied 候选。
                # 2) 布尔/其他：按 lexicon 命中
                if f.lexicon:
                    for term in f.lexicon.denied_terms:
                        if term and term in clause:
                            sig = (f.key, "denied")
                            if sig not in seen:
                                seen.add(sig)
                                out.facts.append(CandidateFact(key=f.key, status="denied", value=None, quote=clause))
                            break
                    else:
                        for term in f.lexicon.present_terms:
                            if term and term in clause:
                                if re.search(_NEG + re.escape(term), neg_clause):
                                    sig = (f.key, "denied")
                                    st = "denied"
                                else:
                                    sig = (f.key, "present")
                                    st = "uncertain" if hedged else "present"
                                if sig not in seen:
                                    seen.add(sig)
                                    if f.type == "bool":
                                        val = True if st != "denied" else None
                                    elif f.type == "text" and st != "denied":
                                        val = clause  # 文本型事实：以患者原句为值
                                    else:
                                        val = None
                                    out.facts.append(CandidateFact(key=f.key, status=st, value=val, quote=clause))
                                break
                # 3) 数值量表：如 "疼痛 7 分"
                if f.type in ("scale", "number"):
                    m = re.search(r"(\d{1,2})\s*分", clause)
                    if m and (f.label[:2] in clause or "疼" in clause or "痛" in clause):
                        sig = (f.key, m.group(1))
                        if sig not in seen:
                            seen.add(sig)
                            out.facts.append(CandidateFact(key=f.key, status="present", value=float(m.group(1)), quote=clause))
        return out

    def narrative(self, fact_lines: list[str], protocol: Protocol) -> str:
        """模板式叙述：按"报告 / 明确否认 / 尚未明确"分桶，不引入任何事实之外的内容。"""
        if not fact_lines:
            return "患者尚未提供可整理的信息。"
        present, denied, unknown = [], [], []
        for line in fact_lines:
            label, _, value = line.partition("：")
            label = re.sub(r"（.*?）", "", label).strip()
            if value.startswith("明确否认"):
                denied.append(label)
            elif value.startswith("未明确"):
                unknown.append(label)
            else:
                present.append(f"{label} {value}")
        parts = []
        if present:
            parts.append("患者报告：" + "；".join(present) + "。")
        if denied:
            parts.append("明确否认：" + "、".join(denied) + "。")
        if unknown:
            parts.append("尚未明确：" + "、".join(unknown) + "。")
        parts.append("以上仅为患者表达的整理，未做医学判断。")
        return "".join(parts)

    def patient_explain(self, doctor_notes: str, protocol: Protocol) -> str:
        """离线模式不改写措辞：把医生要点分条，并按协议里医生审定的术语对照表在术语后加一句大白话；医生的字一个不改。"""
        from ..verification.rewrite_guard import glossary_explain
        return glossary_explain(doctor_notes, protocol.followup.plain_language)[0]


# ------------------------------------------------------------ anthropic
class AnthropicProvider:
    def structured_task(self, kind: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        resp = self._call(kind, lambda: self.client.beta.messages.parse(
            model=self.model, max_tokens=3000, system=system,
            messages=[{"role": "user", "content": user}], output_format=schema,
            output_config={"effort": settings.anthropic_effort_extract}, **self._fallback_kwargs()))
        parsed = getattr(resp, "parsed_output", None)
        if parsed is None:
            raise ProviderError("语义核验没有返回结构化结果")
        return parsed
    """官方 Python SDK。结构化输出用 beta.messages.parse（Pydantic），同一请求上开启：
    - fallbacks="default"（beta server-side-fallback-2026-07-01）：安全分类器误拒时由服务端按类别换模型重跑；
    - system 提示 cache_control：事实清单稳定，重复请求读缓存（低于模型最小缓存长度时自动不缓存，无副作用）；
    - output_config.effort：抽取默认 medium、叙述默认 low（Claude Opus 5 默认开启自适应思考，不传 thinking）。"""

    def __init__(self) -> None:
        import anthropic  # 延迟导入，mock 模式不需要

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(timeout=settings.llm_timeout, max_retries=2)
        self.model = settings.anthropic_model
        self.name = f"anthropic:{self.model}"

    def _fallback_kwargs(self) -> dict:
        if settings.anthropic_fallbacks == "off":
            return {}
        return {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    def _call(self, kind: str, fn):
        a = self._anthropic
        t0 = time.monotonic()
        try:
            resp = fn()
        except a.RateLimitError as e:
            USAGE.errors += 1
            raise ProviderError(f"模型限流（429）：{e.message}") from e
        except a.APIStatusError as e:
            USAGE.errors += 1
            raise ProviderError(f"模型接口错误（{e.status_code}）：{e.message}") from e
        except a.APIConnectionError as e:
            USAGE.errors += 1
            raise ProviderError("模型接口连接失败或超时") from e
        except Exception as e:  # 缺 key 时 SDK 抛 TypeError；参数不被接受、解析失败等也走这里，统一交给兜底
            USAGE.errors += 1
            raise ProviderError(f"模型调用异常：{type(e).__name__}: {str(e)[:200]}") from e
        u = getattr(resp, "usage", None)
        USAGE.add(kind, time.monotonic() - t0, getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0,
                  getattr(u, "cache_read_input_tokens", 0) or 0, getattr(u, "cache_creation_input_tokens", 0) or 0)
        if getattr(resp, "stop_reason", None) == "refusal":
            USAGE.errors += 1
            raise ProviderError("模型拒答（refusal），回退模型也未能完成")
        return resp

    def extract(self, text: str, protocol: Protocol, *, system_text: str | None = None, kind: str = "extract") -> ExtractionOutput:
        system = [{"type": "text", "text": system_text or extraction_system_prompt(protocol), "cache_control": {"type": "ephemeral"}}]
        resp = self._call(kind, lambda: self.client.beta.messages.parse(
            model=self.model,
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": f"患者原话：\n{text}"}],
            output_format=ExtractionOutput,
            output_config={"effort": settings.anthropic_effort_extract},
            **self._fallback_kwargs(),
        ))
        parsed = getattr(resp, "parsed_output", None)
        if parsed is None:
            USAGE.errors += 1
            raise ProviderError(f"结构化输出为空（stop_reason={getattr(resp, 'stop_reason', None)}）")
        return parsed

    def extract_red_flags(self, text: str, protocol: Protocol) -> ExtractionOutput:
        return self.extract(text, protocol, system_text=red_flag_system_prompt(protocol), kind="extract_red_flags")

    def narrative(self, fact_lines: list[str], protocol: Protocol) -> str:
        if not fact_lines:
            return "患者尚未提供可整理的信息。"
        resp = self._call("narrative", lambda: self.client.beta.messages.create(
            model=self.model,
            max_tokens=2000,
            system=NARRATIVE_RULES,
            messages=[{"role": "user", "content": "\n".join(f"- {l}" for l in fact_lines)}],
            output_config={"effort": settings.anthropic_effort_narrative},
            **self._fallback_kwargs(),
        ))
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        if not text:
            raise ProviderError("叙述为空")
        return text

    def patient_explain(self, doctor_notes: str, protocol: Protocol) -> str:
        resp = self._call("patient_explain", lambda: self.client.beta.messages.create(
            model=self.model,
            max_tokens=2000,
            system=PATIENT_REWRITE_RULES,
            messages=[{"role": "user", "content": f"医生要点：\n{doctor_notes}"}],
            output_config={"effort": settings.anthropic_effort_narrative},
            **self._fallback_kwargs(),
        ))
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        if not text:
            raise ProviderError("改写结果为空")
        return text


# ------------------------------------------------------------ compat（国产模型等 OpenAI 兼容接口）
class CompatProvider:
    def structured_task(self, kind: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        output_schema = schema.model_json_schema()
        content = self._chat(kind, [{"role": "system", "content": system + "\n仅输出符合以下 schema 的 JSON：\n" + json.dumps(output_schema, ensure_ascii=False)},
                                    {"role": "user", "content": user}], json_mode=True, schema=output_schema)
        try:
            return schema.model_validate_json(_strip_code_fence(content))
        except (ValidationError, ValueError) as e:
            USAGE.errors += 1
            raise ProviderError("语义核验结果未通过结构校验") from e
    """OpenAI 兼容的 /chat/completions。常见 base_url（以服务商文档为准）：
      DeepSeek     https://api.deepseek.com                         model: deepseek-chat
      通义千问      https://dashscope.aliyuncs.com/compatible-mode/v1 model: qwen-plus / qwen-max
      智谱 GLM     https://open.bigmodel.cn/api/paas/v4              model: glm-4-plus
    输出先按 JSON 解析，再用同一个 Pydantic 模型校验；不合法时把错误回给模型重试一次。"""

    def __init__(self, transport=None) -> None:
        import httpx

        if not (settings.compat_base_url and settings.compat_api_key and settings.compat_model):
            raise ProviderError("compat 模式需要 TIJI_COMPAT_BASE_URL / TIJI_COMPAT_API_KEY / TIJI_COMPAT_MODEL")
        self._httpx = httpx
        self.client = httpx.Client(base_url=settings.compat_base_url.rstrip("/"), timeout=settings.llm_timeout,
                                   headers={"Authorization": f"Bearer {settings.compat_api_key}"}, transport=transport)
        self.model = settings.compat_model
        self.name = f"compat:{self.model}"

    def _chat(self, kind: str, messages: list[dict], json_mode: bool, schema: dict | None = None) -> str:
        body: dict = {"model": self.model, "messages": messages, "temperature": 0}
        if json_mode and settings.compat_json_mode:
            body["response_format"] = {"type": "json_object"}
        t0 = time.monotonic()
        try:
            r = self.client.post("/chat/completions", json=body)
        except self._httpx.HTTPError as e:
            USAGE.errors += 1
            raise ProviderError(f"模型接口连接失败：{type(e).__name__}") from e
        except Exception as e:
            USAGE.errors += 1
            raise ProviderError(f"模型调用异常：{type(e).__name__}: {str(e)[:200]}") from e
        if r.status_code != 200:
            USAGE.errors += 1
            raise ProviderError(f"模型接口错误（{r.status_code}）：{r.text[:200]}")
        try:
            data = r.json()
        except ValueError as e:
            USAGE.errors += 1
            raise ProviderError("模型接口返回的不是 JSON") from e
        u = data.get("usage") or {}
        USAGE.add(kind, time.monotonic() - t0, u.get("prompt_tokens", 0) or 0, u.get("completion_tokens", 0) or 0)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            USAGE.errors += 1
            raise ProviderError("模型返回格式不符合 OpenAI 兼容接口") from e

    def extract(self, text: str, protocol: Protocol, *, system_text: str | None = None, kind: str = "extract") -> ExtractionOutput:
        schema = json.dumps(ExtractionOutput.model_json_schema(), ensure_ascii=False)
        messages = [
            {"role": "system", "content": (system_text or extraction_system_prompt(protocol))
             + "\n\n只输出一个 JSON 对象，符合以下 JSON Schema，不要输出任何其它文字：\n" + schema},
            {"role": "user", "content": f"患者原话：\n{text}"},
        ]
        last_err = ""
        for _ in range(2):
            content = self._chat(kind, messages, json_mode=True)
            try:
                return ExtractionOutput.model_validate_json(_strip_code_fence(content))
            except ValidationError as e:
                last_err = str(e)[:800]
                messages = messages + [{"role": "assistant", "content": content},
                                       {"role": "user", "content": "上面的输出不符合 Schema：" + last_err + "\n请只输出修正后的 JSON。"}]
        USAGE.errors += 1
        raise ProviderError("结构化输出两次校验失败：" + last_err[:200])

    def extract_red_flags(self, text: str, protocol: Protocol) -> ExtractionOutput:
        return self.extract(text, protocol, system_text=red_flag_system_prompt(protocol), kind="extract_red_flags")

    def narrative(self, fact_lines: list[str], protocol: Protocol) -> str:
        if not fact_lines:
            return "患者尚未提供可整理的信息。"
        text = self._chat("narrative", [{"role": "system", "content": NARRATIVE_RULES},
                                         {"role": "user", "content": "\n".join(f"- {l}" for l in fact_lines)}], json_mode=False)
        text = text.strip()
        if not text:
            raise ProviderError("叙述为空")
        return text

    def patient_explain(self, doctor_notes: str, protocol: Protocol) -> str:
        text = self._chat("patient_explain", [{"role": "system", "content": PATIENT_REWRITE_RULES},
                                               {"role": "user", "content": f"医生要点：\n{doctor_notes}"}], json_mode=False).strip()
        if not text:
            raise ProviderError("改写结果为空")
        return text


class OllamaProvider(CompatProvider):
    """本机模型（Ollama 原生 /api/chat）：患者原话不离开这台电脑。和走兼容接口相比：
      - 能设上下文长度：Ollama 默认 4096，装不下抽取提示词（约 5 千字），前半截会被截掉；
      - 能关掉思考（qwen3 用 false；gpt-oss 关不掉，用 low），否则一句话也要输出几百个思考词元；
      - 抽取时把 JSON Schema 交给服务端做约束解码，输出一定是合法 JSON，再用同一个 Pydantic 模型校验。"""

    def __init__(self, transport=None) -> None:
        import httpx

        if not settings.ollama_model:
            raise ProviderError("ollama 模式需要 TIJI_OLLAMA_MODEL（例如 qwen3:4b、gpt-oss:20b）")
        self._httpx = httpx
        self.client = httpx.Client(base_url=settings.ollama_base_url.rstrip("/"), timeout=settings.llm_timeout, transport=transport)
        self.model = settings.ollama_model
        self.name = f"ollama:{self.model}"
        t = settings.ollama_think.strip().lower()
        self.think: bool | str = {"false": False, "0": False, "true": True, "1": True}.get(t, t)

    def _chat(self, kind: str, messages: list[dict], json_mode: bool, schema: dict | None = None) -> str:
        body: dict = {"model": self.model, "messages": messages, "stream": False, "think": self.think, "keep_alive": "60m",
                      "options": {"num_ctx": settings.ollama_num_ctx, "temperature": 0, "num_predict": 3000}}
        if json_mode:
            body["format"] = schema or ExtractionOutput.model_json_schema()
        t0 = time.monotonic()
        try:
            r = self.client.post("/api/chat", json=body)
        except self._httpx.HTTPError as e:
            USAGE.errors += 1
            raise ProviderError(f"本机模型连接失败：{type(e).__name__}（Ollama 是否在运行？）") from e
        except Exception as e:
            USAGE.errors += 1
            raise ProviderError(f"模型调用异常：{type(e).__name__}: {str(e)[:200]}") from e
        if r.status_code != 200:
            USAGE.errors += 1
            raise ProviderError(f"本机模型接口错误（{r.status_code}）：{r.text[:200]}")
        try:
            data = r.json()
        except ValueError as e:
            USAGE.errors += 1
            raise ProviderError("本机模型返回的不是 JSON") from e
        USAGE.add(kind, time.monotonic() - t0, data.get("prompt_eval_count", 0) or 0, data.get("eval_count", 0) or 0)
        content = (data.get("message") or {}).get("content")
        if not isinstance(content, str):
            USAGE.errors += 1
            raise ProviderError("本机模型返回格式不符合 Ollama /api/chat")
        return content

    # 本地模式下模型只做抽取与红旗专查；叙述与给患者的说明用确定性模板（不调用模型、不会混进思考过程）
    def narrative(self, fact_lines: list[str], protocol: Protocol) -> str:
        return MockProvider().narrative(fact_lines, protocol)

    def patient_explain(self, doctor_notes: str, protocol: Protocol) -> str:
        return MockProvider().patient_explain(doctor_notes, protocol)


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.S)
    return m.group(1) if m else s


# ------------------------------------------------------------ 兜底
class UnavailableProvider:
    def structured_task(self, kind: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        raise ProviderError(self.reason)
    """真实模型构建失败（缺配置、缺依赖）时的占位：每次调用都抛 ProviderError，由 ResilientProvider 退回离线词表。
    这样配置错了也不会让患者端 500，而且顶栏与 /api/health 会写明"未就绪"的原因。"""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason

    def extract(self, text: str, protocol: Protocol) -> ExtractionOutput:
        raise ProviderError(self.reason)

    def narrative(self, fact_lines: list[str], protocol: Protocol) -> str:
        raise ProviderError(self.reason)

    def patient_explain(self, doctor_notes: str, protocol: Protocol) -> str:
        raise ProviderError(self.reason)


class ResilientProvider:
    def structured_task(self, kind: str, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        try:
            result = self.primary.structured_task(kind, system, user, schema)
        except Exception as e:
            self._degrade(kind, e)
            raise ProviderError("语义核验暂不可用，请由医护核实") from e
        self.last_used = self.primary.name
        return result
    """真实模型失败时退回离线词表，并把 provider 名标成 "mock(fallback)"，界面与摘要都能看到。

    捕获一切异常，而不只是 ProviderError：患者端永远不该因为模型出错拿到 500（第二轮评审实测：没有 key 时
    SDK 抛 TypeError，旧版只捕获 ProviderError，患者在"描述"一步直接 500）。错误写日志、计入 USAGE，
    最近一次错误保存在 last_error，/api/health 与医生端顶栏可见。评测时 TIJI_LLM_FALLBACK=none，不经过这里。"""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary, self.fallback = primary, fallback
        self.name = primary.name
        self.last_used = primary.name
        self.last_error: str | None = None
        self.last_error_at: str | None = None

    def _degrade(self, kind: str, e: Exception) -> None:
        if not isinstance(e, ProviderError):  # ProviderError 在抛出处已计数
            USAGE.errors += 1
        USAGE.fallbacks += 1
        self.last_used = "mock(fallback)"
        self.last_error = f"{type(e).__name__}: {str(e)[:300]}"
        self.last_error_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        log.warning("真实模型 %s 失败，已退回离线词表：%s", kind, self.last_error)

    def extract(self, text: str, protocol: Protocol) -> ExtractionOutput:
        try:
            out = self.primary.extract(text, protocol)
        except Exception as e:  # noqa: BLE001 — 兜底必须覆盖所有异常
            self._degrade("extract", e)
            return self.fallback.extract(text, protocol)
        self.last_used = self.primary.name
        return out

    def extract_red_flags(self, text: str, protocol: Protocol) -> ExtractionOutput:
        """红旗专查只是加一道保险：主模型没有这一步或调用失败时返回空结果，不影响主抽取与问卷兜底。"""
        fn = getattr(self.primary, "extract_red_flags", None)
        if fn is None or self.last_used == "mock(fallback)":
            return ExtractionOutput()
        try:
            return fn(text, protocol)
        except Exception as e:  # noqa: BLE001
            if not isinstance(e, ProviderError):
                USAGE.errors += 1
            log.warning("红旗专查失败，已跳过（问卷红旗一屏仍会直接问）：%s: %s", type(e).__name__, str(e)[:200])
            return ExtractionOutput()

    def narrative(self, fact_lines: list[str], protocol: Protocol) -> str:
        try:
            out = self.primary.narrative(fact_lines, protocol)
        except Exception as e:  # noqa: BLE001
            self._degrade("narrative", e)
            return self.fallback.narrative(fact_lines, protocol)
        self.last_used = self.primary.name
        return out

    def patient_explain(self, doctor_notes: str, protocol: Protocol) -> str:
        try:
            out = self.primary.patient_explain(doctor_notes, protocol)
        except Exception as e:  # noqa: BLE001
            self._degrade("patient_explain", e)
            return self.fallback.patient_explain(doctor_notes, protocol)
        self.last_used = self.primary.name
        return out


_provider: LLMProvider | None = None
_lock = threading.Lock()
REAL_PROVIDERS = ("anthropic", "compat", "ollama")


def build_provider(name: str | None = None) -> LLMProvider:
    name = name or settings.llm_provider
    if name not in REAL_PROVIDERS:
        return MockProvider()
    try:
        primary: LLMProvider = {"anthropic": AnthropicProvider, "compat": CompatProvider, "ollama": OllamaProvider}[name]()
    except Exception as e:  # noqa: BLE001
        if settings.llm_fallback != "mock":
            raise  # 评测：配置错误如实暴露
        reason = f"{name} 模型未就绪：{type(e).__name__}: {str(e)[:200]}"
        log.warning(reason)
        primary = UnavailableProvider(f"{name}:未就绪", reason)
    return ResilientProvider(primary, MockProvider()) if settings.llm_fallback == "mock" else primary


def get_provider() -> LLMProvider:
    global _provider
    with _lock:
        if _provider is None:
            _provider = build_provider()
        return _provider


def reset_provider() -> None:
    """测试与自检用：丢弃已构建的提供者，下次按当前配置重建。"""
    global _provider
    with _lock:
        _provider = None


# ------------------------------------------------------------ 连通性自检
PROBE_TEXT = "腰疼三天了，弯腰的时候更疼，没有腿麻。"
_LAST_PROBE: dict = {}


def credentials_hint() -> str | None:
    """只说"有没有配置"，不回显任何密钥内容。"""
    import os

    if settings.llm_provider == "anthropic":
        has = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
        return "已配置 ANTHROPIC_API_KEY" if has else "未发现 ANTHROPIC_API_KEY"
    if settings.llm_provider == "compat":
        missing = [n for n, v in (("TIJI_COMPAT_BASE_URL", settings.compat_base_url), ("TIJI_COMPAT_API_KEY", settings.compat_api_key),
                                  ("TIJI_COMPAT_MODEL", settings.compat_model)) if not v]
        return "兼容接口三项已配置" if not missing else "缺少 " + " / ".join(missing)
    if settings.llm_provider == "ollama":
        return f"本机模型 {settings.ollama_base_url}（数据不出本机）" if settings.ollama_model else "缺少 TIJI_OLLAMA_MODEL"
    return None


def probe(protocol: Protocol | None = None) -> dict:
    """真实模型连通性自检：用一句固定的测试原话跑一次真实抽取（绕过兜底），报告能否用、耗时、抽到几条、引文是否逐字。
    只在手动自检时调用（make llm-check、make demo 启动时、医生端顶栏"自检"），不放进每次健康检查，避免空耗费用。"""
    result: dict = {"provider": settings.llm_provider, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "credentials": credentials_hint()}
    if settings.llm_provider not in REAL_PROVIDERS:
        result.update(ok=True, mode="mock", detail="当前为离线词表模式，不调用真实模型")
    else:
        if protocol is None:
            from ..protocol.loader import get_protocol
            protocol = get_protocol(settings.default_protocol_id)
        p = get_provider()
        primary = getattr(p, "primary", p)
        result["name"] = getattr(primary, "name", settings.llm_provider)
        t0 = time.monotonic()
        try:
            out = primary.extract(PROBE_TEXT, protocol)
        except Exception as e:  # noqa: BLE001
            result.update(ok=False, seconds=round(time.monotonic() - t0, 2), detail=f"{type(e).__name__}: {str(e)[:300]}")
        else:
            bad = [c.quote for c in out.facts if c.quote not in PROBE_TEXT]
            n = len(out.facts)
            result.update(ok=n > 0 and not bad, seconds=round(time.monotonic() - t0, 2), facts=n,
                          detail=f"测试原话抽到 {n} 条候选事实" + (f"；{len(bad)} 条引文不在原文中" if bad else ""))
    _LAST_PROBE.clear()
    _LAST_PROBE.update(result)
    return result


def provider_info() -> dict:
    p = get_provider()
    primary = getattr(p, "primary", p)
    return {"provider": settings.llm_provider, "name": getattr(primary, "name", getattr(p, "name", "mock")),
            "fallback": settings.llm_fallback if settings.llm_provider != "mock" else None,
            "last_used": getattr(p, "last_used", getattr(p, "name", "mock")),
            "ready": not isinstance(primary, UnavailableProvider) and not (credentials_hint() or "").startswith(("未发现", "缺少")),
            "not_ready_reason": getattr(primary, "reason", None),
            "last_error": getattr(p, "last_error", None), "last_error_at": getattr(p, "last_error_at", None),
            "credentials": credentials_hint(),
            "usage": {"calls": USAGE.calls, "errors": USAGE.errors, "fallbacks": USAGE.fallbacks},
            "last_probe": dict(_LAST_PROBE) or None}
