from __future__ import annotations


class ModelVersion:
    def __init__(self, major: int, minor: int, patch: int) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump_major(self) -> ModelVersion:
        return ModelVersion(self.major + 1, 0, 0)

    def bump_minor(self) -> ModelVersion:
        return ModelVersion(self.major, self.minor + 1, 0)

    def bump_patch(self) -> ModelVersion:
        return ModelVersion(self.major, self.minor, self.patch + 1)
