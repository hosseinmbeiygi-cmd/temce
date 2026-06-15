from __future__ import annotations

from enum import StrEnum


class StorageType(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    MEMORY = "memory"


class StorageFormat(StrEnum):
    PARQUET = "parquet"
    CSV = "csv"
    JSON = "json"
    AVRO = "avro"
    ORC = "orc"
    PICKLE = "pickle"
    HDF5 = "hdf5"


class CompressionType(StrEnum):
    NONE = "none"
    GZIP = "gzip"
    SNAPPY = "snappy"
    ZSTD = "zstd"
    LZ4 = "lz4"
    BROTLI = "brotli"


class RetentionPolicy(StrEnum):
    KEEP_ALL = "keep_all"
    KEEP_LAST_N = "keep_last_n"
    KEEP_BY_AGE = "keep_by_age"
    KEEP_BY_SIZE = "keep_by_size"
    ARCHIVE_AFTER = "archive_after"
