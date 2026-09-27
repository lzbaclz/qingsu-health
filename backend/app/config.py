"""运行配置。所有配置都可通过环境变量覆盖（见 backend/.env.example）。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]  # 仓库根目录 delinbei/


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    # 非演示环境拒绝未批准协议；本地演示须由启动命令显式指定。
    app_mode: str = field(default_factory=lambda: _env("TIJI_MODE", "production"))
    session_hours: int = field(default_factory=lambda: int(_env("TIJI_SESSION_HOURS", "8")))
    invite_hours: int = field(default_factory=lambda: int(_env("TIJI_INVITE_HOURS", "72")))
    worker_interval_seconds: float = field(default_factory=lambda: float(_env("TIJI_WORKER_INTERVAL", "30")))
    delivery_config: str = field(default_factory=lambda: _env("TIJI_DELIVERY_CONFIG", ""))
    # LLM：mock（默认，离线可跑、可复现）| anthropic（官方 SDK）| compat（国产模型等 OpenAI 兼容接口）| ollama（本机模型）
    llm_provider: str = field(default_factory=lambda: _env("TIJI_LLM_PROVIDER", "mock"))
    # 真实模型调用失败时的兜底：mock = 退回离线词表并在界面标注；none = 直接报错（评测时用，避免掩盖失败）
    llm_fallback: str = field(default_factory=lambda: _env("TIJI_LLM_FALLBACK", "mock"))
    llm_timeout: float = field(default_factory=lambda: float(_env("TIJI_LLM_TIMEOUT", "90")))
    anthropic_model: str = field(default_factory=lambda: _env("TIJI_ANTHROPIC_MODEL", "claude-opus-5"))
    # effort：抽取关系到红旗与"不编造"，默认 medium；叙述只是改写，默认 low。可用评测比较后再调。
    anthropic_effort_extract: str = field(default_factory=lambda: _env("TIJI_ANTHROPIC_EFFORT_EXTRACT", "medium"))
    anthropic_effort_narrative: str = field(default_factory=lambda: _env("TIJI_ANTHROPIC_EFFORT_NARRATIVE", "low"))
    # 服务端拒答回退（Claude Opus 5 建议默认开启）：default = 由 Anthropic 按拒答类别选择回退模型；off = 关闭
    anthropic_fallbacks: str = field(default_factory=lambda: _env("TIJI_ANTHROPIC_FALLBACKS", "default"))
    compat_base_url: str = field(default_factory=lambda: _env("TIJI_COMPAT_BASE_URL", ""))
    compat_api_key: str = field(default_factory=lambda: _env("TIJI_COMPAT_API_KEY", ""))
    compat_model: str = field(default_factory=lambda: _env("TIJI_COMPAT_MODEL", ""))
    compat_json_mode: bool = field(default_factory=lambda: _env("TIJI_COMPAT_JSON_MODE", "1") == "1")
    # 本机模型（Ollama 原生接口）：数据不出门诊电脑。num_ctx 要装得下抽取提示词（约 5 千字），默认 16384；
    # think：qwen3 等用 false 关掉思考；gpt-oss 不能关，用 low
    ollama_base_url: str = field(default_factory=lambda: _env("TIJI_OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("TIJI_OLLAMA_MODEL", ""))
    ollama_num_ctx: int = field(default_factory=lambda: int(_env("TIJI_OLLAMA_NUM_CTX", "16384")))
    ollama_think: str = field(default_factory=lambda: _env("TIJI_OLLAMA_THINK", "false"))
    database_url: str = field(
        default_factory=lambda: _env("TIJI_DATABASE_URL", f"sqlite:///{ROOT / 'backend' / 'tiji.db'}")
    )
    protocol_dir: Path = field(default_factory=lambda: Path(_env("TIJI_PROTOCOL_DIR", str(ROOT / "protocols"))))
    default_protocol_id: str = field(default_factory=lambda: _env("TIJI_DEFAULT_PROTOCOL", "lbp_adult_v0.2"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in _env("TIJI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        )
    )
    # 可用性测试：在任务卡 A/B 植入一次"错抽"，统计真人在一键核对里点"不对"的比例（make user-test-backend 打开；演示与评测关闭）
    user_test_plant: bool = field(default_factory=lambda: _env("TIJI_USER_TEST_PLANT", "0") == "1")
    # 给患者说明的改写方式（第三轮评审 T5）：glossary = 医生审定的术语对照表，不调用模型（默认）；
    # llm = 由模型改写措辞，要点以外的新内容在发送前被拦下，并自动加 AI 标注
    patient_rewrite: str = field(default_factory=lambda: _env("TIJI_PATIENT_REWRITE", "glossary"))
    # 门诊本地时区（服务时段按它判断）；演示时钟：TIJI_DEMO_NOW=2026-10-15T22:47:00+08:00 把"现在"拨到指定时刻
    clinic_tz: str = field(default_factory=lambda: _env("TIJI_CLINIC_TZ", "Asia/Shanghai"))
    demo_now: str = field(default_factory=lambda: _env("TIJI_DEMO_NOW", ""))
    # 允许 /api/dev/* 演示接口（生产必须关闭）
    enable_dev_endpoints: bool = field(default_factory=lambda: _env("TIJI_ENABLE_DEV", "0") == "1" and _env("TIJI_MODE", "production") == "demo")


settings = Settings()
