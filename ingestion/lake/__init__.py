from __future__ import annotations

import asyncio
import hashlib
import io
import uuid
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from ingestion.config import IngestionConfig

logger = get_logger(__name__)


class RawDataLake:
    def __init__(self, config: IngestionConfig) -> None:
        self._config = config
        self._client: Any = None

    async def start(self) -> None:
        from minio import Minio

        endpoint = self._config.lake_endpoint.replace("http://", "").replace("https://", "")
        self._client = Minio(
            endpoint,
            access_key=self._config.lake_access_key,
            secret_key=self._config.lake_secret_key,
            secure=self._config.lake_endpoint.startswith("https"),
        )
        for bucket in (self._config.lake_bucket_raw, self._config.lake_bucket_parsed):
            exists = await asyncio.to_thread(self._client.bucket_exists, bucket)
            if not exists:
                await asyncio.to_thread(self._client.make_bucket, bucket)
                logger.info("Created bucket: %s", bucket)

    async def store_raw(
        self,
        source: str,
        endpoint: str,
        data: bytes,
        content_type: str,
        fetch_time: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if self._client is None:
            raise RuntimeError("RawDataLake not started")

        content_hash = hashlib.sha256(data).hexdigest()
        object_id = str(uuid.uuid4())
        ts = (fetch_time or datetime.now(UTC)).strftime("%Y%m%d/%H%M%S")
        object_key = f"{source}/{ts}/{object_id}_{content_hash[:16]}.bin"

        meta = {
            "source": source,
            "endpoint": endpoint,
            "content_type": content_type,
            "content_hash": content_hash,
            "fetch_time": (fetch_time or datetime.now(UTC)).isoformat(),
        }
        if metadata:
            meta.update(metadata)

        buf = io.BytesIO(data)
        await asyncio.to_thread(
            self._client.put_object,
            self._config.lake_bucket_raw,
            object_key,
            buf,
            len(data),
            content_type=content_type,
            metadata=meta,
        )
        logger.debug("Stored raw payload: %s/%s", self._config.lake_bucket_raw, object_key)
        return object_key

    async def get_raw(self, object_key: str) -> bytes | None:
        if self._client is None:
            raise RuntimeError("RawDataLake not started")
        try:
            resp = await asyncio.to_thread(
                self._client.get_object,
                self._config.lake_bucket_raw,
                object_key,
            )
            return resp.read()
        except Exception:
            logger.exception("Failed to read raw object: %s", object_key)
            return None

    async def list_raw(self, source: str, date_prefix: str | None = None) -> list[str]:
        if self._client is None:
            raise RuntimeError("RawDataLake not started")
        prefix = f"{source}/"
        if date_prefix:
            prefix = f"{source}/{date_prefix}"
        objects = await asyncio.to_thread(
            self._client.list_objects,
            self._config.lake_bucket_raw,
            prefix=prefix,
        )
        return [o.object_name for o in objects]
