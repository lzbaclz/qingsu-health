from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import hashlib
import re

import yaml
from pydantic import ValidationError

from ..config import settings
from .schema import Protocol


def _protocol_path(protocol_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}", protocol_id):
        raise ValueError("非法协议标识")
    return settings.protocol_dir / f"{protocol_id}.yaml"


def protocol_digest(protocol_id: str) -> str:
    return hashlib.sha256(_protocol_path(protocol_id).read_bytes()).hexdigest()


def get_protocol(protocol_id: str) -> Protocol:
    path = _protocol_path(protocol_id)
    if not path.exists():
        raise FileNotFoundError(f"协议不存在: {path}")
    return _load_protocol(path.read_bytes())


@lru_cache(maxsize=32)
def _load_protocol(content: bytes) -> Protocol:
    data = yaml.safe_load(content)
    p = Protocol.model_validate(data)
    p.content_sha256 = hashlib.sha256(content).hexdigest()
    return p


def for_encounter(session, encounter) -> Protocol:
    """已创建就诊沿用不可变协议快照；修改默认协议不能悄悄改变既有流程。"""
    from ..models import ProtocolSnapshot
    if encounter.protocol_sha256:
        snap = session.get(ProtocolSnapshot, encounter.protocol_sha256)
        if snap:
            p = Protocol.model_validate(snap.content)
            p.content_sha256 = snap.id
            return p
        raise ValueError("该就诊的协议快照缺失，请联系管理员恢复备份")
    # 旧演示数据没有快照；允许查看，但不伪称原始版本已被重建。
    return get_protocol(encounter.protocol_id)


def list_protocols() -> list[dict]:
    out = []
    for p in sorted(settings.protocol_dir.glob("*.yaml")):
        if p.stem == "body_regions":
            continue
        try:
            proto = get_protocol(p.stem)
            out.append({
                "protocol_id": proto.protocol_id, "version": proto.version, "status": proto.status,
                "title": proto.title, "specialty": proto.specialty,
                "facts": len(proto.facts), "questions": len(proto.questions), "red_flags": len(proto.red_flags),
                "review_gaps": len(proto.review_gaps()),
            })
        except Exception as e:  # noqa: BLE001
            out.append({"protocol_id": p.stem, "error": str(e)})
    return out


def validate_protocol_text(text: str) -> dict:
    """供 /api/protocols/validate 使用：医生改完 YAML 立刻知道哪里不合法。"""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return {"ok": False, "errors": [f"YAML 解析失败: {e}"]}
    try:
        proto = Protocol.model_validate(data)
    except ValidationError as e:
        return {"ok": False, "errors": [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]}
    return {"ok": True, "errors": [], "protocol_id": proto.protocol_id, "version": proto.version,
            "review_gaps": proto.review_gaps()}


@lru_cache(maxsize=1)
def load_body_regions() -> list[dict]:
    path = settings.protocol_dir / "body_regions.yaml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)["regions"]


def region_index() -> dict[str, dict]:
    return {r["id"]: r for r in load_body_regions()}
