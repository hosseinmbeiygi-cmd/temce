from __future__ import annotations

from datetime import datetime

import json

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.result import PaginatedResult, Result
from domain.common.base_entity import BaseEntity
from domain.common.enum_types import ModelStage
from domain.ml.entities import ModelVersion, TrainingRun
from models.ml import MlModelModel, MlModelVersionModel, MlTrainingRunModel
from repositories.base_repository import InMemoryRepository
from repositories.db_base import DbRepository


class MlModel(BaseEntity):
    def __init__(
        self,
        id: str,
        name: str,
        task: str = "classification",
        framework: str = "sklearn",
        latest_version: str = "1.0.0",
        description: str = "",
        tags: list[str] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.task = task
        self.framework = framework
        self.latest_version = latest_version
        self.description = description
        self.tags = tags or []


class MlRepository:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._mem_model: InMemoryRepository[MlModel] | None = None if session else InMemoryRepository[MlModel]()
        self._mem_version: InMemoryRepository[ModelVersion] | None = None if session else InMemoryRepository[ModelVersion]()
        self._mem_run: InMemoryRepository[TrainingRun] | None = None if session else InMemoryRepository[TrainingRun]()
        self._db: _MlDbRepo | None = None if not session else _MlDbRepo(session)

    async def get_model(self, id: str) -> Result[MlModel]:
        if self._db:
            return await self._db.get_model(id)
        return await self._mem_model.get(id)

    async def save_model(self, entity: MlModel) -> Result[MlModel]:
        if self._db:
            return await self._db.save_model(entity)
        return await self._mem_model.save(entity)

    async def delete_model(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete_model(id)
        return await self._mem_model.delete(id)

    async def list_models(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[MlModel]]:
        if self._db:
            return await self._db.list_models(page, page_size)
        return await self._mem_model.list(page, page_size)

    async def get_model_by_name(self, name: str) -> Result[MlModel]:
        if self._db:
            return await self._db.get_model_by_name(name)
        for m in self._mem_model._store.values():
            if m.name == name:
                return Result.ok(m)
        return Result.fail(f"ML model {name} not found")

    async def get_version(self, id: str) -> Result[ModelVersion]:
        if self._db:
            return await self._db.get_version(id)
        return await self._mem_version.get(id)

    async def save_version(self, entity: ModelVersion) -> Result[ModelVersion]:
        if self._db:
            return await self._db.save_version(entity)
        return await self._mem_version.save(entity)

    async def delete_version(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete_version(id)
        return await self._mem_version.delete(id)

    async def get_versions_by_model(self, model_id: str) -> Result[list[ModelVersion]]:
        if self._db:
            return await self._db.get_versions_by_model(model_id)
        matches = [v for v in self._mem_version._store.values() if v.id.startswith(model_id)]
        return Result.ok(matches)

    async def get_latest_version(self, model_id: str) -> Result[ModelVersion]:
        if self._db:
            return await self._db.get_latest_version(model_id)
        matches = [v for v in self._mem_version._store.values() if v.id.startswith(model_id)]
        if not matches:
            return Result.fail(f"No versions for model {model_id}")
        return Result.ok(sorted(matches, key=lambda v: v.version, reverse=True)[0])

    async def get_training_run(self, id: str) -> Result[TrainingRun]:
        if self._db:
            return await self._db.get_training_run(id)
        return await self._mem_run.get(id)

    async def save_training_run(self, entity: TrainingRun) -> Result[TrainingRun]:
        if self._db:
            return await self._db.save_training_run(entity)
        return await self._mem_run.save(entity)

    async def delete_training_run(self, id: str) -> Result[bool]:
        if self._db:
            return await self._db.delete_training_run(id)
        return await self._mem_run.delete(id)

    async def list_training_runs(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[TrainingRun]]:
        if self._db:
            return await self._db.list_training_runs(page, page_size)
        return await self._mem_run.list(page, page_size)

    async def get_training_runs_by_status(self, status: str) -> Result[list[TrainingRun]]:
        if self._db:
            return await self._db.get_training_runs_by_status(status)
        matches = [r for r in self._mem_run._store.values() if r.status == status]
        return Result.ok(matches)

    async def count_models(self) -> int:
        if self._db:
            return await self._db.count_models()
        return len(self._mem_model._store)


class _MlDbRepo(DbRepository):
    model_class = None

    async def get_model(self, id: str) -> Result[MlModel]:
        stmt = select(MlModelModel).where(MlModelModel.id == id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"MlModel {id} not found")
        return Result.ok(self._model_to_domain(row))

    async def save_model(self, entity: MlModel) -> Result[MlModel]:
        orm = self._model_to_orm(entity)
        self.session.add(orm)
        await self.session.flush()
        return Result.ok(self._model_to_domain(orm))

    async def delete_model(self, id: str) -> Result[bool]:
        stmt = select(MlModelModel).where(MlModelModel.id == id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"MlModel {id} not found")
        await self.session.delete(row)
        return Result.ok(True)

    async def list_models(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[MlModel]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(MlModelModel)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = select(MlModelModel).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok(
            PaginatedResult(
                items=[self._model_to_domain(r) for r in rows],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_model_by_name(self, name: str) -> Result[MlModel]:
        stmt = select(MlModelModel).where(MlModelModel.name == name)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"ML model {name} not found")
        return Result.ok(self._model_to_domain(row))

    async def get_version(self, id: str) -> Result[ModelVersion]:
        stmt = select(MlModelVersionModel).where(MlModelVersionModel.id == id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"ModelVersion {id} not found")
        return Result.ok(self._version_to_domain(row))

    async def save_version(self, entity: ModelVersion) -> Result[ModelVersion]:
        orm = self._version_to_orm(entity)
        self.session.add(orm)
        await self.session.flush()
        return Result.ok(self._version_to_domain(orm))

    async def delete_version(self, id: str) -> Result[bool]:
        stmt = select(MlModelVersionModel).where(MlModelVersionModel.id == id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"ModelVersion {id} not found")
        await self.session.delete(row)
        return Result.ok(True)

    async def get_versions_by_model(self, model_id: str) -> Result[list[ModelVersion]]:
        stmt = select(MlModelVersionModel).where(MlModelVersionModel.model_id == model_id).order_by(desc(MlModelVersionModel.version))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._version_to_domain(r) for r in rows])

    async def get_latest_version(self, model_id: str) -> Result[ModelVersion]:
        stmt = (
            select(MlModelVersionModel)
            .where(MlModelVersionModel.model_id == model_id)
            .order_by(desc(MlModelVersionModel.version))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"No versions for model {model_id}")
        return Result.ok(self._version_to_domain(row))

    async def get_training_run(self, id: str) -> Result[TrainingRun]:
        stmt = select(MlTrainingRunModel).where(MlTrainingRunModel.id == id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"TrainingRun {id} not found")
        return Result.ok(self._run_to_domain(row))

    async def save_training_run(self, entity: TrainingRun) -> Result[TrainingRun]:
        orm = self._run_to_orm(entity)
        self.session.add(orm)
        await self.session.flush()
        return Result.ok(self._run_to_domain(orm))

    async def delete_training_run(self, id: str) -> Result[bool]:
        stmt = select(MlTrainingRunModel).where(MlTrainingRunModel.id == id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return Result.fail(f"TrainingRun {id} not found")
        await self.session.delete(row)
        return Result.ok(True)

    async def list_training_runs(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[TrainingRun]]:
        from sqlalchemy import func as sa_func

        count_stmt = select(sa_func.count()).select_from(MlTrainingRunModel)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = select(MlTrainingRunModel).order_by(desc(MlTrainingRunModel.created_at)).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok(
            PaginatedResult(
                items=[self._run_to_domain(r) for r in rows],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    async def get_training_runs_by_status(self, status: str) -> Result[list[TrainingRun]]:
        stmt = select(MlTrainingRunModel).where(MlTrainingRunModel.status == status).order_by(desc(MlTrainingRunModel.created_at))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return Result.ok([self._run_to_domain(r) for r in rows])

    async def count_models(self) -> int:
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(MlModelModel)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _model_to_domain(self, orm: MlModelModel) -> MlModel:
        tags = []
        if orm.tags:
            try:
                tags = json.loads(orm.tags)
            except (json.JSONDecodeError, TypeError):
                tags = [s.strip() for s in orm.tags.split(",") if s.strip()]
        return MlModel(
            id=orm.id,
            name=orm.name,
            task=orm.task or "classification",
            framework=orm.framework or "sklearn",
            latest_version=orm.latest_version or "1.0.0",
            description=orm.description or "",
            tags=tags,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _model_to_orm(self, domain: MlModel) -> MlModelModel:
        return MlModelModel(
            id=domain.id,
            name=domain.name,
            task=domain.task or "classification",
            framework=domain.framework or "sklearn",
            latest_version=domain.latest_version or "1.0.0",
            description=domain.description or None,
            tags=json.dumps(domain.tags, ensure_ascii=False) if domain.tags else None,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    def _version_to_domain(self, orm: MlModelVersionModel) -> ModelVersion:
        metrics = {}
        if orm.metrics:
            try:
                metrics = json.loads(orm.metrics)
            except (json.JSONDecodeError, TypeError):
                pass
        params = {}
        if orm.parameters:
            try:
                params = json.loads(orm.parameters)
            except (json.JSONDecodeError, TypeError):
                pass
        stage = ModelStage(orm.stage) if orm.stage else ModelStage.DEVELOPMENT
        return ModelVersion(
            id=orm.id,
            model_name=orm.model_id,
            version=orm.version,
            stage=stage,
            metrics=metrics,
            parameters=params,
            artifact_path=orm.artifact_path or "",
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _version_to_orm(self, domain: ModelVersion) -> MlModelVersionModel:
        return MlModelVersionModel(
            id=domain.id,
            model_id=domain.model_name,
            version=domain.version,
            stage=domain.stage.value if domain.stage else "development",
            metrics=json.dumps(domain.metrics, ensure_ascii=False) if domain.metrics else None,
            parameters=json.dumps(domain.parameters, ensure_ascii=False) if domain.parameters else None,
            artifact_path=domain.artifact_path or None,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )

    def _run_to_domain(self, orm: MlTrainingRunModel) -> TrainingRun:
        config = {}
        if orm.config:
            try:
                config = json.loads(orm.config)
            except (json.JSONDecodeError, TypeError):
                pass
        run_metrics = {}
        if orm.metrics:
            try:
                run_metrics = json.loads(orm.metrics)
            except (json.JSONDecodeError, TypeError):
                pass
        return TrainingRun(
            id=orm.id,
            model_version_id=orm.id,
            status=orm.status or "pending",
            start_time=orm.started_at,
            end_time=orm.finished_at,
            hyperparameters=config,
            metrics=run_metrics,
            error_message=orm.error or "",
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _run_to_orm(self, domain: TrainingRun) -> MlTrainingRunModel:
        return MlTrainingRunModel(
            id=domain.id,
            experiment_name="",
            run_name="",
            status=domain.status or "pending",
            config=json.dumps(domain.hyperparameters, ensure_ascii=False) if domain.hyperparameters else None,
            metrics=json.dumps(domain.metrics, ensure_ascii=False) if domain.metrics else None,
            started_at=domain.start_time,
            finished_at=domain.end_time,
            error=domain.error_message or None,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
