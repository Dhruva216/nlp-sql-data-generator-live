from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from nlp_sql.config import AppConfig
from nlp_sql.deps import get_app_config
from nlp_sql.rules_store import DynamicRule, RulesStore

router = APIRouter()


class CreateRuleRequest(BaseModel):
    category: str = Field(..., description="Category (e.g. TableMapping, FieldMapping, RoleRule, CustomInstruction)")
    rule_name: str = Field(..., description="Short identifier name for rule")
    rule_content: str = Field(..., description="The prompt rule instruction text")
    role_id: Optional[int] = Field(default=None, description="Optional RoleId scope (NULL=Global, 1=Admin, 2=Student, 3=Instructor)")
    is_active: bool = Field(default=True, description="Whether rule is active")
    display_order: int = Field(default=0, description="Display order sequence")


class UpdateRuleRequest(BaseModel):
    category: Optional[str] = None
    rule_name: Optional[str] = None
    rule_content: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


@router.get("", response_model=list[DynamicRule])
def list_rules(
    category: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active_only: bool = False,
    config: AppConfig = Depends(get_app_config),
) -> list[DynamicRule]:
    """Retrieve all dynamic rules from database store."""
    if is_active_only:
        rules = RulesStore.get_active_rules(config, role_id=role_id)
    else:
        rules = RulesStore.get_all_rules(config)

    if category:
        rules = [r for r in rules if r.category.lower() == category.lower()]
    if role_id is not None and not is_active_only:
        rules = [r for r in rules if r.role_id is None or r.role_id == role_id]

    return rules


@router.post("", response_model=DynamicRule)
def create_rule(
    body: CreateRuleRequest,
    config: AppConfig = Depends(get_app_config),
) -> DynamicRule:
    """Create a new dynamic query rule / condition in database."""
    try:
        return RulesStore.create_rule(
            config,
            category=body.category,
            rule_name=body.rule_name,
            rule_content=body.rule_content,
            role_id=body.role_id,
            is_active=body.is_active,
            display_order=body.display_order,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create rule: {e}") from e


@router.put("/{rule_id}", response_model=dict[str, str])
def update_rule(
    rule_id: int,
    body: UpdateRuleRequest,
    config: AppConfig = Depends(get_app_config),
) -> dict[str, str]:
    """Update an existing rule in the database."""
    ok = RulesStore.update_rule(
        config,
        rule_id=rule_id,
        category=body.category,
        rule_name=body.rule_name,
        rule_content=body.rule_content,
        role_id=body.role_id,
        is_active=body.is_active,
        display_order=body.display_order,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"Rule ID {rule_id} not found or connection error")
    return {"status": "ok", "message": f"Rule {rule_id} updated successfully"}


@router.delete("/{rule_id}", response_model=dict[str, str])
def delete_rule(
    rule_id: int,
    config: AppConfig = Depends(get_app_config),
) -> dict[str, str]:
    """Delete a rule from database store."""
    ok = RulesStore.delete_rule(config, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Rule ID {rule_id} not found")
    return {"status": "ok", "message": f"Rule {rule_id} deleted successfully"}
