from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_active_user, require_role
from app.db.session import get_session_dependency
from app.db.models import ThreatRule, ThreatRuleType, ThreatRuleSeverity, Zone, Camera, User, UserRole
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rules", tags=["rules"])


class ThreatRuleBase(BaseModel):
    name: str
    rule_type: ThreatRuleType
    severity: ThreatRuleSeverity = ThreatRuleSeverity.MEDIUM
    is_active: bool = True
    config_json: dict = {}
    cooldown_seconds: int = 60
    model_version: Optional[str] = None


class ThreatRuleCreate(ThreatRuleBase):
    camera_id: int
    zone_id: Optional[int] = None


class ThreatRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[ThreatRuleType] = None
    severity: Optional[ThreatRuleSeverity] = None
    is_active: Optional[bool] = None
    config_json: Optional[dict] = None
    cooldown_seconds: Optional[int] = None
    model_version: Optional[str] = None


class ThreatRuleResponse(ThreatRuleBase):
    id: int
    camera_id: int
    zone_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ThreatRuleListResponse(BaseModel):
    items: List[ThreatRuleResponse]
    total: int
    page: int
    page_size: int


@router.post("", response_model=ThreatRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: ThreatRuleCreate,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> ThreatRule:
    query = select(Camera).where(Camera.id == rule_data.camera_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    camera = (await session.execute(query)).scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    if rule_data.zone_id:
        zone = await session.get(Zone, rule_data.zone_id)
        if not zone or zone.camera_id != rule_data.camera_id:
            raise HTTPException(status_code=400, detail="Zone not found or not on this camera")

    rule = ThreatRule(**rule_data.model_dump())
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    logger.info("Rule created", rule_id=rule.id, camera_id=rule.camera_id, type=rule.rule_type)
    return rule


@router.get("", response_model=ThreatRuleListResponse)
async def list_rules(
    camera_id: Optional[int] = None,
    rule_type: Optional[ThreatRuleType] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> ThreatRuleListResponse:
    query = select(ThreatRule).join(Camera)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    if camera_id:
        query = query.where(ThreatRule.camera_id == camera_id)
    if rule_type:
        query = query.where(ThreatRule.rule_type == rule_type)
    if is_active is not None:
        query = query.where(ThreatRule.is_active == is_active)

    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(ThreatRule.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    rules = result.scalars().all()

    return ThreatRuleListResponse(items=list(rules), total=total, page=page, page_size=page_size)


@router.get("/{rule_id}", response_model=ThreatRuleResponse)
async def get_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> ThreatRule:
    query = select(ThreatRule).join(Camera).where(ThreatRule.id == rule_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.patch("/{rule_id}", response_model=ThreatRuleResponse)
async def update_rule(
    rule_id: int,
    rule_data: ThreatRuleUpdate,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> ThreatRule:
    query = select(ThreatRule).join(Camera).where(ThreatRule.id == rule_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = rule_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    await session.commit()
    await session.refresh(rule)
    logger.info("Rule updated", rule_id=rule.id, by=current_user.id)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> None:
    query = select(ThreatRule).join(Camera).where(ThreatRule.id == rule_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await session.delete(rule)
    await session.commit()
    logger.info("Rule deleted", rule_id=rule_id, by=current_user.id)