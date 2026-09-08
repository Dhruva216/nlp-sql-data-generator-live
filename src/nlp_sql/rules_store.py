from __future__ import annotations

import logging
import time
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine

from nlp_sql.config import AppConfig
from nlp_sql.engine_map import build_engines

logger = logging.getLogger(__name__)


class DynamicRule(BaseModel):
    rule_id: int
    category: str
    rule_name: str
    rule_content: str
    role_id: Optional[int] = None
    is_active: bool = True
    display_order: int = 0


class RulesStore:
    """Fetches and caches dynamic rules from database table (dbo.NLP_SQL_Rules)."""

    _cache: dict[str, tuple[float, list[DynamicRule]]] = {}
    _cache_ttl_seconds: float = 60.0  # 1 minute TTL cache

    @classmethod
    def invalidate_cache(cls) -> None:
        """Clear cached rules across all roles."""
        cls._cache.clear()

    @classmethod
    def get_default_engine(cls, config: AppConfig) -> Engine | None:
        try:
            engines = build_engines(config)
            if not engines:
                return None
            # Return first engine (e.g. mssql_live)
            return next(iter(engines.values()))
        except Exception as e:
            logger.warning(f"Could not build engine for rules store: {e}")
            return None

    @classmethod
    def get_active_rules(
        cls, config: AppConfig, role_id: int | None = None
    ) -> list[DynamicRule]:
        cache_key = f"role_{role_id}"
        now = time.time()

        # Return cached rules if TTL hasn't expired
        if cache_key in cls._cache:
            ts, rules = cls._cache[cache_key]
            if now - ts < cls._cache_ttl_seconds:
                return rules

        engine = cls.get_default_engine(config)
        if engine is None:
            return []

        try:
            query = text(
                "SELECT RuleId, Category, RuleName, RuleContent, RoleId, IsActive, DisplayOrder "
                "FROM dbo.NLP_SQL_Rules "
                "WHERE IsActive = 1 AND (RoleId IS NULL OR RoleId = :role_id) "
                "ORDER BY DisplayOrder ASC, RuleId ASC"
            )
            with engine.connect() as conn:
                res = conn.execute(query, {"role_id": role_id if role_id is not None else 1})
                rows = res.fetchall()

            rules = [
                DynamicRule(
                    rule_id=row[0],
                    category=str(row[1]),
                    rule_name=str(row[2]),
                    rule_content=str(row[3]),
                    role_id=row[4],
                    is_active=bool(row[5]),
                    display_order=int(row[6]),
                )
                for row in rows
            ]
            cls._cache[cache_key] = (now, rules)
            return rules
        except Exception as e:
            # Fallback gracefully if table does not exist yet or query fails
            logger.info(f"dbo.NLP_SQL_Rules table query fallback: {e}")
            return []

    @classmethod
    def get_all_rules(cls, config: AppConfig) -> list[DynamicRule]:
        """Fetch all rules including inactive ones for administrative management API."""
        engine = cls.get_default_engine(config)
        if engine is None:
            return []

        try:
            query = text(
                "SELECT RuleId, Category, RuleName, RuleContent, RoleId, IsActive, DisplayOrder "
                "FROM dbo.NLP_SQL_Rules "
                "ORDER BY Category ASC, DisplayOrder ASC, RuleId ASC"
            )
            with engine.connect() as conn:
                res = conn.execute(query)
                rows = res.fetchall()

            return [
                DynamicRule(
                    rule_id=row[0],
                    category=str(row[1]),
                    rule_name=str(row[2]),
                    rule_content=str(row[3]),
                    role_id=row[4],
                    is_active=bool(row[5]),
                    display_order=int(row[6]),
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching all rules: {e}")
            return []

    @classmethod
    def create_rule(
        cls,
        config: AppConfig,
        category: str,
        rule_name: str,
        rule_content: str,
        role_id: int | None = None,
        is_active: bool = True,
        display_order: int = 0,
    ) -> DynamicRule:
        engine = cls.get_default_engine(config)
        if engine is None:
            raise RuntimeError("Database connection unavailable")

        query = text(
            "INSERT INTO dbo.NLP_SQL_Rules (Category, RuleName, RuleContent, RoleId, IsActive, DisplayOrder) "
            "VALUES (:cat, :name, :content, :role, :active, :order)"
        )
        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "cat": category,
                    "name": rule_name,
                    "content": rule_content,
                    "role": role_id,
                    "active": 1 if is_active else 0,
                    "order": display_order,
                },
            )
            # Fetch inserted ID
            res = conn.execute(text("SELECT MAX(RuleId) FROM dbo.NLP_SQL_Rules"))
            new_id = res.scalar() or 1

        cls.invalidate_cache()
        return DynamicRule(
            rule_id=new_id,
            category=category,
            rule_name=rule_name,
            rule_content=rule_content,
            role_id=role_id,
            is_active=is_active,
            display_order=display_order,
        )

    @classmethod
    def update_rule(
        cls,
        config: AppConfig,
        rule_id: int,
        category: Optional[str] = None,
        rule_name: Optional[str] = None,
        rule_content: Optional[str] = None,
        role_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        display_order: Optional[int] = None,
    ) -> bool:
        engine = cls.get_default_engine(config)
        if engine is None:
            return False

        updates = []
        params: dict[str, Any] = {"rule_id": rule_id}
        if category is not None:
            updates.append("Category = :cat")
            params["cat"] = category
        if rule_name is not None:
            updates.append("RuleName = :name")
            params["name"] = rule_name
        if rule_content is not None:
            updates.append("RuleContent = :content")
            params["content"] = rule_content
        if role_id is not None:
            updates.append("RoleId = :role")
            params["role"] = role_id
        if is_active is not None:
            updates.append("IsActive = :active")
            params["active"] = 1 if is_active else 0
        if display_order is not None:
            updates.append("DisplayOrder = :order")
            params["order"] = display_order

        if not updates:
            return True

        query_str = f"UPDATE dbo.NLP_SQL_Rules SET {', '.join(updates)} WHERE RuleId = :rule_id"
        with engine.begin() as conn:
            conn.execute(text(query_str), params)

        cls.invalidate_cache()
        return True

    @classmethod
    def delete_rule(cls, config: AppConfig, rule_id: int) -> bool:
        engine = cls.get_default_engine(config)
        if engine is None:
            return False

        query = text("DELETE FROM dbo.NLP_SQL_Rules WHERE RuleId = :rule_id")
        with engine.begin() as conn:
            conn.execute(query, {"rule_id": rule_id})

        cls.invalidate_cache()
        return True
