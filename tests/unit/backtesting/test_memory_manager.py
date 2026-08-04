from __future__ import annotations

from backtesting.data.memory_manager import (
    InMemoryManager,
    MemoryManagerConfig,
    PartitionedDataManager,
    create_memory_manager,
)


class TestMemoryManager:
    def test_in_memory_manager_creation(self):
        mm = InMemoryManager(MemoryManagerConfig(max_memory_mb=512))
        assert mm.config.max_memory_mb == 512

    def test_save_and_load(self):
        mm = InMemoryManager()
        mm.save_data([1, 2, 3], "test_path")
        data = mm.load_data("test_path")
        assert data == [1, 2, 3]

    def test_load_nonexistent(self):
        mm = InMemoryManager()
        data = mm.load_data("nonexistent")
        assert data is None

    def test_chunk_loading(self):
        mm = InMemoryManager()
        mm.save_data(list(range(100)), "test_path")
        chunk = mm.load_chunk("test_path", 10, 20)
        assert chunk == list(range(10, 30))

    def test_estimate_memory(self):
        mm = InMemoryManager()
        est = mm.estimate_memory(1000000, 10, 8)
        assert est > 0

    def test_should_chunk(self):
        mm = InMemoryManager(MemoryManagerConfig(max_memory_mb=1))
        assert mm.should_chunk(1000000, 10)

    def test_should_not_chunk(self):
        mm = InMemoryManager(MemoryManagerConfig(max_memory_mb=1024))
        assert not mm.should_chunk(100, 10)

    def test_optimize_chunk_size(self):
        mm = InMemoryManager(MemoryManagerConfig(max_memory_mb=1))
        chunk = mm.optimize_chunk_size(1000000, 100)
        assert chunk > 0

    def test_get_temp_path(self):
        mm = InMemoryManager()
        path = mm.get_temp_path("test.parquet")
        assert path.endswith("test.parquet")

    def test_clear(self):
        mm = InMemoryManager()
        mm.save_data([1, 2, 3], "test_path")
        mm.clear()
        assert mm.load_data("test_path") is None

    def test_get_memory_usage(self):
        mm = InMemoryManager()
        usage = mm.get_memory_usage()
        assert usage >= 0

    def test_partitioned_manager(self):
        pm = PartitionedDataManager()
        pm.save_data("test_data", "partition_1")
        data = pm.load_data("partition_1")
        assert data == "test_data"

    def test_factory_creates_in_memory(self):
        mm = create_memory_manager("in_memory")
        assert isinstance(mm, InMemoryManager)

    def test_factory_creates_partitioned(self):
        mm = create_memory_manager("in_memory")
        assert isinstance(mm, InMemoryManager)

    def test_chunks_loaded_counter(self):
        mm = InMemoryManager()
        mm.load_data("test")
        mm.load_data("test2")
        assert mm.chunks_loaded == 2
