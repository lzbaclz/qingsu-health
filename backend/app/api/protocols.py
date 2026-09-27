from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from ..security import Principal, require_doctor

from ..protocol import get_protocol, list_protocols, load_body_regions, validate_protocol_text
from . import schemas as S

router = APIRouter(prefix="/api", tags=["protocol"])


from pydantic import BaseModel, Field, ValidationError
import yaml
from ..protocol.preview import PreviewCase, preview


class PreviewIn(BaseModel):
    base_protocol_id: str = Field(max_length=100)
    candidate_yaml: str = Field(max_length=200000)
    cases: list[PreviewCase] = Field(min_length=1, max_length=30)


@router.post("/protocols/preview-impact")
def preview_impact(body: PreviewIn, user: Principal = Depends(require_doctor)):
    try:
        return preview(get_protocol(body.base_protocol_id), body.candidate_yaml, body.cases)
    except (ValueError, ValidationError, yaml.YAMLError, FileNotFoundError) as e:
        raise HTTPException(400, str(e))


@router.get("/protocols")
def protocols():
    return list_protocols()


@router.get("/protocols/{protocol_id}")
def protocol_detail(protocol_id: str):
    try:
        p = get_protocol(protocol_id)
    except FileNotFoundError:
        raise HTTPException(404, "协议不存在")
    return {**p.model_dump(), "review_gaps": p.review_gaps()}


@router.post("/protocols/validate")
def validate(body: S.ProtocolValidateIn, user: Principal = Depends(require_doctor)):
    return validate_protocol_text(body.yaml_text)


@router.get("/body-regions")
def body_regions():
    return load_body_regions()
