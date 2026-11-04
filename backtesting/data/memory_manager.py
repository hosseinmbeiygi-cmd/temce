from __future__ import annotations

import gc
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from core.time import now_utc


class StorageFormat(StrEnum):
    PARQUET = "parquet"
    ARROW = "arrow"
    CSV = "csv"
    JSON = "json"
    IN_MEMORY = "in_memory"


class CompressionType(StrEnum):
    NONE = "none"
    SNAPPY = "snappy"
    GZIP = "gzip"
    ZSTD = "zstd"
    LZ4 = "lz4"


@dataclass
class PartitionConfig:
    enabled: bool = True
    partition_by: str = "date"
    partition_granularity: str = "month"
    max_rows_per_partition: int = 1_000_000


@dataclass
class MemoryManagerConfig:
    max_memory_mb: int = 1024
    chunk_size: int = 10_000
    storage_format: StorageFormat = StorageFormat.IN_MEMORY
    compression: CompressionType = CompressionType.SNAPPY
    temp_dir: str = ""
    enable_gc: bool = True
    gc_interval: int = 100
    partition_config: PartitionConfig = field(default_factory=PartitionConfig)
    use_mmap: bool = False


class MemoryManager(ABC):
    def __init__(self, config: MemoryManagerConfig | None = None) -> None:
        self._config = config or MemoryManagerConfig()
        self._chunks_loaded = 0
        self._memory_usage: list[dict[str, Any]] = []
        self._gc_counter = 0

    @property
    def config(self) -> MemoryManagerConfig:
        return self._config

    @property
    def chunks_loaded(self) -> int:
        return self._chunks_loaded

    @abstractmethod
    def load_data(self, path: str, columns: list[str] | None = None) -> Any: ...

    @abstractmethod
    def save_data(self, data: Any, path: str, format: StorageFormat | None = None) -> None: ...

    @abstractmethod
    def load_chunk(self, path: str, offset: int, limit: int) -> Any: ...

    @abstractmethod
    def get_memory_usage(self) -> float: ...

    def estimate_memory(self, num_rows: int, num_cols: int, dtype_size: int = 8) -> float:
        return num_rows * num_cols * dtype_size / (1024 * 1024)

    def should_chunk(self, num_rows: int, num_cols: int) -> bool:
        est_mb = self.estimate_memory(num_rows, num_cols)
        return est_mb > self._config.max_memory_mb * 0.8

    def optimize_chunk_size(self, num_rows: int, num_cols: int) -> int:
        est_mb = self.estimate_memory(num_rows, num_cols)
        if est_mb <= self._config.max_memory_mb:
            return num_rows
        ratio = self._config.max_memory_mb / est_mb
        return max(self._config.chunk_size, int(num_rows * ratio * 0.9))

    def get_temp_path(self, filename: str) -> str:
        temp_dir = self._config.temp_dir or tempfile.gettempdir()
        return os.path.join(temp_dir, filename)

    def _check_gc(self) -> None:
        if not self._config.enable_gc:
            return
        self._gc_counter += 1
        if self._gc_counter >= self._config.gc_interval:
            gc.collect()
            self._gc_counter = 0
            self._memory_usage.append({
                "timestamp": now_utc(),
                "gc_collected": gc.get_count(),
                "memory_mb": self.get_memory_usage(),
            })


class InMemoryManager(MemoryManager):
    def __init__(self, config: MemoryManagerConfig | None = None) -> None:
        super().__init__(config)
        self._data: dict[str, Any] = {}

    def load_data(self, path: str, columns: list[str] | None = None) -> Any:
        self._chunks_loaded += 1
        self._check_gc()
        return self._data.get(path)

    def save_data(self, data: Any, path: str, format: StorageFormat | None = None) -> None:
        self._data[path] = data

    def load_chunk(self, path: str, offset: int, limit: int) -> Any:
        data = self._data.get(path)
        if data is None:
            return None
        if isinstance(data, list):
            return data[offset : offset + limit]
        return data

    def get_memory_usage(self) -> float:
        import sys
        total = 0.0
        for key, val in self._data.items():
            total += sys.getsizeof(key) + sys.getsizeof(val)
        return total / (1024 * 1024)

    def clear(self) -> None:
        self._data.clear()
        gc.collect()


class PartitionedDataManager(MemoryManager):
    def __init__(self, config: MemoryManagerConfig | None = None) -> None:
        super().__init__(config)
        self._partitions: dict[str, Any] = {}

    def _get_partition_key(self, timestamp: datetime) -> str:
        cfg = self._config.partition_config
        if cfg.partition_granularity == "year":
            return str(timestamp.year)
        if cfg.partition_granularity == "month":
            return f"{timestamp.year}-{timestamp.month:02d}"
        if cfg.partition_granularity == "week":
            iso = timestamp.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        return str(timestamp.date())

    def load_data(self, path: str, columns: list[str] | None = None) -> Any:
        self._chunks_loaded += 1
        self._check_gc()
        return self._partitions.get(path)

    def save_data(self, data: Any, path: str, format: StorageFormat | None = None) -> None:
        self._partitions[path] = data

    def load_chunk(self, path: str, offset: int, limit: int) -> Any:
        data = self._partitions.get(path)
        if data is None:
            return None
        if isinstance(data, list):
            return data[offset : offset + limit]
        return data

    def get_memory_usage(self) -> float:
        import sys
        total = 0.0
        for key, val in self._partitions.items():
            total += sys.getsizeof(key) + sys.getsizeof(val)
        return total / (1024 * 1024)

    def clear(self) -> None:
        self._partitions.clear()
        gc.collect()


def create_memory_manager(
    storage_format: str = "in_memory",
    max_memory_mb: int = 1024,
) -> MemoryManager:
    config = MemoryManagerConfig(
        max_memory_mb=max_memory_mb,
        storage_format=StorageFormat(storage_format),
    )
    if storage_format == "in_memory":
        return InMemoryManager(config)
    return PartitionedDataManager(config)
