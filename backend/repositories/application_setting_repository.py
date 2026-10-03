"""Data access for global and per-user settings."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.application_setting import ApplicationSetting


class ApplicationSettingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, scope_key: str, namespace: str) -> ApplicationSetting | None:
        result = await self.db.execute(
            select(ApplicationSetting).where(
                ApplicationSetting.scope_key == scope_key,
                ApplicationSetting.namespace == namespace,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        scope_key: str,
        namespace: str,
        data: dict[str, Any],
        updated_by_user_id: int,
    ) -> ApplicationSetting:
        setting = await self.get(scope_key, namespace)
        if setting is None:
            setting = ApplicationSetting(
                scope_key=scope_key,
                namespace=namespace,
                data=data,
                updated_by_user_id=updated_by_user_id,
            )
            self.db.add(setting)
        else:
            setting.data = data
            setting.updated_by_user_id = updated_by_user_id
        await self.db.flush()
        return setting

    async def merge(
        self,
        scope_key: str,
        namespace: str,
        patch: dict[str, Any],
        updated_by_user_id: int,
    ) -> ApplicationSetting:
        current = await self.get(scope_key, namespace)
        merged = dict(current.data or {}) if current else {}
        merged.update(patch)
        return await self.upsert(scope_key, namespace, merged, updated_by_user_id)
