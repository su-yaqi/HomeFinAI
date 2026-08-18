from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlmodel import Session

from app.core.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIRMATION_ENV = "CONFIRM_LEGACY_AI_RETIREMENT"
CONFIRMATION_VALUE = "PERMANENTLY_DISABLE_LEGACY_AI"
RECENT_USE_DAYS = 90


def audit_legacy_ai_access(session: Session) -> list[dict[str, Any]]:
    table_name = session.execute(
        text("SELECT to_regclass('public.apitoken')")
    ).scalar_one()
    if table_name is None:
        logger.info("Legacy API Token table does not exist; no retirement impact")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_USE_DAYS)
    rows = (
        session.execute(
            text(
                """
            SELECT name, token_prefix, is_active, created_by, last_used_at
            FROM apitoken
            WHERE is_active = true OR last_used_at >= :cutoff
            ORDER BY is_active DESC, last_used_at DESC NULLS LAST, name
            """
            ).bindparams(cutoff=cutoff)
        )
        .mappings()
        .all()
    )
    total = session.execute(text("SELECT count(*) FROM apitoken")).scalar_one()
    active = session.execute(
        text("SELECT count(*) FROM apitoken WHERE is_active = true")
    ).scalar_one()
    logger.info(
        "Legacy AI retirement impact: total=%s active=%s recently_used=%s observation_days=%s",
        total,
        active,
        len(
            [
                row
                for row in rows
                if row["last_used_at"] is not None and row["last_used_at"] >= cutoff
            ]
        ),
        RECENT_USE_DAYS,
    )
    report = [dict(row) for row in rows]
    for row in report:
        logger.warning(
            "Legacy integration affected: name=%s prefix=%s active=%s created_by=%s last_used_at=%s",
            row["name"],
            row["token_prefix"],
            row["is_active"],
            row["created_by"],
            row["last_used_at"],
        )
    return report


def enforce_retirement_confirmation(
    affected: list[dict[str, Any]], confirmation: str | None
) -> None:
    if affected and confirmation != CONFIRMATION_VALUE:
        raise RuntimeError(
            "Active or recently used legacy AI integrations will be permanently disabled. "
            f"Review the impact report and set {CONFIRMATION_ENV}={CONFIRMATION_VALUE} "
            "for this deployment only to confirm the v0.9 cutover."
        )


def main() -> None:
    with Session(engine) as session:
        affected = audit_legacy_ai_access(session)
    enforce_retirement_confirmation(affected, os.getenv(CONFIRMATION_ENV))
    if affected:
        logger.warning(
            "Legacy AI retirement was explicitly confirmed for this deployment"
        )
    else:
        logger.info(
            "No active or recently used legacy AI integrations block retirement"
        )


if __name__ == "__main__":
    main()
