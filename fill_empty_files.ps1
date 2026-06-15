$root = "C:\Users\Mohadese\Desktop\New folder (2)"
$emptyFiles = Get-ChildItem -Path $root -Recurse -File -Filter "*.py" | Where-Object { $_.Length -eq 0 }

$count = 0
foreach ($file in $emptyFiles) {
    $relPath = $file.FullName.Replace("$root\", "").Replace("\", "/")
    $dir = $file.Directory.Name
    $parentDir = $file.Directory.Parent.Name
    $grandParent = $file.Directory.Parent.Parent.Name
    $fileName = $file.Name

    if ($fileName -eq "__init__.py") {
        # Get sibling .py files (non-init)
        $siblings = Get-ChildItem -Path $file.Directory.FullName -File -Filter "*.py" | Where-Object { $_.Name -ne "__init__.py" -and $_.Length -gt 0 }
        $names = @()
        foreach ($s in $siblings) {
            $module = [System.IO.Path]::GetFileNameWithoutExtension($s.Name)
            $names += $module
        }
        if ($names.Count -gt 0) {
            $imports = ""
            $all = ""
            foreach ($n in $names) {
                $snake = $n -replace '_', '_'
                $imports += "from .$snake import *`n"
                $all += "`"$snake`", "
            }
            $allList = $all.TrimEnd(', ')
            Set-Content -Path $file.FullName -Value "$imports`n__all__ = [$allList]"
        } else {
            # Check subdirectories
            $subdirs = Get-ChildItem -Path $file.Directory.FullName -Directory
            if ($subdirs.Count -gt 0) {
                $imports = ""
                $all = ""
                foreach ($sd in $subdirs) {
                    $subInit = Join-Path $sd.FullName "__init__.py"
                    if (Test-Path $subInit) {
                        $snake = $sd.Name
                        $imports += "from .$snake import *`n"
                        $all += "`"$snake`", "
                    }
                }
                $allList = $all.TrimEnd(', ')
                if ($allList) {
                    Set-Content -Path $file.FullName -Value "$imports`n__all__ = [$allList]"
                } else {
                    Set-Content -Path $file.FullName -Value "# $relPath"
                }
            } else {
                Set-Content -Path $file.FullName -Value "# $relPath"
            }
        }
    }
    elseif ($fileName -match "^(.+)_provider\.py$") {
        $name = $matches[1]
        $className = ($name -replace '(?:^|_)(.)', { $_.Groups[1].Value.ToUpper() }) + "Provider"
        Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from providers.base.base_provider import BaseProvider
from core.result import Result

class $className(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="$name")

    async def fetch(self, **kwargs: Any) -> Result[Any]:
        return Result.fail("Not implemented")

    async def health(self) -> dict[str, Any]:
        return {"status": "unknown", "provider": "$name"}
"@
    }
    elseif ($fileName -match "^(.+)_repository\.py$") {
        $name = $matches[1]
        $className = ($name -replace '(?:^|_)(.)', { $_.Groups[1].Value.ToUpper() }) + "Repository"
        Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from repositories.base_repository import InMemoryRepository
from domain.$name import $(if (Test-Path "$root\domain\$name") { "..." } else { "..." })
from core.result import Result

class $className(InMemoryRepository):
    pass
"@
    }
    elseif ($fileName -match "^(.+)_service\.py$" -and $parentDir -eq "" -or !$parentDir) {
        $name = $matches[1]
        $className = ($name -replace '(?:^|_)(.)', { $_.Groups[1].Value.ToUpper() }) + "Service"
        Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.result import Result
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    async def execute(self, **kwargs: Any) -> Result[Any]:
        return Result.fail("Not implemented")
"@
    }
    elseif ($fileName -match "^(.+)_model\.py$" -or $fileName -match "^(.+)\.py$") {
        # Generic model/feature/... file
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($fileName)
        $className = ($stem -replace '(?:^|_)(.)', { $_.Groups[1].Value.ToUpper() })
        if ($relPath -match "ml/models/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from ml.models.base import BaseModel
from ml.types import FeatureMatrix, TargetVector, PredictionResult

class $className(BaseModel):
    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        import numpy as np
        return PredictionResult(predictions=np.zeros(X.shape[0]), model_id=self.name)

    def save(self, path: str) -> None:
        pass

    def load(self, path: str) -> None:
        pass
"@
        }
        elseif ($relPath -match "backtesting/strategies/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent

class $className(BaseStrategy):
    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        return []
"@
        }
        elseif ($relPath -match "backtesting/engine/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "backtesting/metrics/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
import numpy as np

class $className:
    @staticmethod
    def compute(data: Any) -> dict[str, float]:
        return {}
"@
        }
        elseif ($relPath -match "backtesting/risk/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "backtesting/signals/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any

class $className:
    pass
"@
        }
        elseif ($relPath -match "ml/features/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
import pandas as pd
from ml.features.base import BaseFeatureBuilder
from ml.types import FeatureMatrix

class $className(BaseFeatureBuilder):
    def compute(self, data: pd.DataFrame) -> FeatureMatrix:
        return FeatureMatrix(data=data)

    def get_feature_names(self) -> list[str]:
        return []
"@
        }
        elseif ($relPath -match "ml/training/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "ml/evaluation/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
import numpy as np

class $className:
    pass
"@
        }
        elseif ($relPath -match "ml/inference/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "ml/registry/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "ml/monitoring/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "ml/explainability/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any

class $className:
    def explain(self, model: Any, features: Any) -> dict[str, Any]:
        return {}
"@
        }
        elseif ($relPath -match "pipelines/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.result import Result
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    async def process(self, data: Any) -> Result[Any]:
        return Result.ok(data)
"@
        }
        elseif ($relPath -match "monitoring/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "integrations/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "providers/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from providers.base.base_provider import BaseProvider
from core.result import Result

class $className(BaseProvider):
    async def fetch(self, **kwargs: Any) -> Result[Any]:
        return Result.fail("Not implemented")

    async def health(self) -> dict[str, Any]:
        return {"status": "unknown"}
"@
        }
        elseif ($relPath -match "domain/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from domain.common.base_entity import BaseEntity

@dataclass
class $className(BaseEntity):
    def __init__(self, id: str, **kwargs: Any) -> None:
        super().__init__(id)
"@
        }
        elseif ($relPath -match "apps/.*worker.*tasks/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

async def run(**kwargs: Any) -> dict[str, Any]:
    logger.info("Task $stem started")
    return {"status": "completed", "task": "$stem"}
"@
        }
        elseif ($relPath -match "apps/.*worker/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from core.logging import get_logger

logger = get_logger(__name__)

def main() -> None:
    logger.info("Starting worker")
"@
        }
        elseif ($relPath -match "apps/admin_api/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from fastapi import APIRouter
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()
"@
        }
        elseif ($relPath -match "apps/admin_ui/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from core.logging import get_logger

logger = get_logger(__name__)
"@
        }
        elseif ($relPath -match "apps/api/routes/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from fastapi import APIRouter, Depends
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()
"@
        }
        elseif ($relPath -match "apps/scheduler/schedules/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from core.logging import get_logger

logger = get_logger(__name__)
"@
        }
        elseif ($relPath -match "reports/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    def build(self, data: Any) -> Any:
        return data
"@
        }
        elseif ($relPath -match "schemas/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from pydantic import BaseModel
from typing import Any

class $className(BaseModel):
    pass
"@
        }
        elseif ($relPath -match "storage/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        elseif ($relPath -match "tests/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
import pytest
from core.logging import get_logger

logger = get_logger(__name__)
"@
        }
        elseif ($relPath -match "migrations/") {
            Set-Content -Path $file.FullName -Value @"""
Migration script.
"""
"@
        }
        elseif ($relPath -match "scripts/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from core.logging import get_logger

logger = get_logger(__name__)

def main() -> None:
    logger.info("Script $stem executed")
"@
        }
        elseif ($relPath -match "core/") {
            Set-Content -Path $file.FullName -Value @"
from __future__ import annotations
from typing import Any
from core.logging import get_logger

logger = get_logger(__name__)

class $className:
    pass
"@
        }
        else {
            Set-Content -Path $file.FullName -Value "# $relPath"
        }
    }
    else {
        Set-Content -Path $file.FullName -Value "# $relPath"
    }

    $count++
    if ($count % 100 -eq 0) {
        Write-Host "Filled $count files..."
    }
}

Write-Host "Done! Filled $count empty files."
