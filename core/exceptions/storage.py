from __future__ import annotations

from core.exceptions import InfrastructureError


class StorageError(InfrastructureError):
    def __init__(self, message: str = "Storage error", code: str = "STORAGE_ERROR") -> None:
        super().__init__(message=message)
        self.code = code


class FileNotFoundError(StorageError):
    def __init__(self, path: str = "") -> None:
        super().__init__(message=f"File not found: {path}", code="FILE_NOT_FOUND")


class FileWriteError(StorageError):
    def __init__(self, path: str = "", message: str = "Failed to write file") -> None:
        super().__init__(message=f"{message}: {path}", code="FILE_WRITE_ERROR")


class FileReadError(StorageError):
    def __init__(self, path: str = "", message: str = "Failed to read file") -> None:
        super().__init__(message=f"{message}: {path}", code="FILE_READ_ERROR")


class StorageQuotaExceeded(StorageError):
    def __init__(self, message: str = "Storage quota exceeded") -> None:
        super().__init__(message=message, code="STORAGE_QUOTA_EXCEEDED")


class UnsupportedStorageBackend(StorageError):
    def __init__(self, backend: str = "") -> None:
        super().__init__(message=f"Unsupported storage backend: {backend}", code="UNSUPPORTED_BACKEND")
