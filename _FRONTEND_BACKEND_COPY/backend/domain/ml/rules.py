from __future__ import annotations

from domain.common.enum_types import ModelStage


def validate_model_stage_transition(current: ModelStage, target: ModelStage) -> bool:
    transitions = {
        ModelStage.DEVELOPMENT: [ModelStage.STAGING, ModelStage.ARCHIVED],
        ModelStage.STAGING: [ModelStage.PRODUCTION, ModelStage.DEVELOPMENT, ModelStage.ARCHIVED],
        ModelStage.PRODUCTION: [ModelStage.ARCHIVED, ModelStage.DEPRECATED],
        ModelStage.ARCHIVED: [],
        ModelStage.DEPRECATED: [ModelStage.ARCHIVED],
    }
    return target in transitions.get(current, [])


def validate_confidence(confidence: float) -> bool:
    return 0.0 <= confidence <= 1.0


def validate_probability(probability: float) -> bool:
    return 0.0 <= probability <= 1.0


def is_model_deployable(stage: ModelStage) -> bool:
    return stage == ModelStage.PRODUCTION


def is_model_active(stage: ModelStage) -> bool:
    return stage not in (ModelStage.ARCHIVED, ModelStage.DEPRECATED)
