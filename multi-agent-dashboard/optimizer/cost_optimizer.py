"""Cost optimizer for selecting optimal models based on task requirements."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from .task_classifier import TaskClassification, TaskType, Requirements
from .model_database import (
    ModelDatabase,
    ModelSpec,
    QualityTier,
    SpeedTier,
    get_model_database,
)


@dataclass
class ModelRecommendation:
    model_id: str
    provider: str
    display_name: str
    total_cost: float
    input_cost: float
    output_cost: float
    quality_tier: str
    speed_tier: str
    context_limit: int
    meets_requirements: bool
    score: float  # Combined quality/cost score
    notes: List[str] = field(default_factory=list)


@dataclass
class OptimizationResult:
    recommendations: List[ModelRecommendation]
    best_choice: Optional[ModelRecommendation]
    task_type: TaskType
    complexity_score: float
    input_tokens: int
    estimated_output_tokens: int
    quality_requirement: QualityTier
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CostOptimizer:
    """Calculate optimal model for task at lowest cost."""

    QUALITY_VALUES = {
        QualityTier.HIGHEST: 4,
        QualityTier.HIGH: 3,
        QualityTier.MEDIUM: 2,
        QualityTier.LOW: 1,
    }

    SPEED_VALUES = {
        SpeedTier.VERY_FAST: 4,
        SpeedTier.FAST: 3,
        SpeedTier.MEDIUM: 2,
        SpeedTier.SLOW: 1,
    }

    # Task type to capability mapping
    TASK_CAPABILITIES = {
        TaskType.CODE: "code",
        TaskType.CREATIVE: "creative",
        TaskType.REASONING: "reasoning",
        TaskType.TRANSLATION: "translation",
        TaskType.MULTIMODAL: "multimodal",
        TaskType.GENERAL: None,
    }

    def __init__(self, model_db: Optional[ModelDatabase] = None):
        self.model_db = model_db or get_model_database()

    def optimize(
        self,
        classification: TaskClassification,
        input_tokens: int,
        estimated_output_tokens: Optional[int] = None,
    ) -> OptimizationResult:
        """Find best model by cost for required quality."""
        # Estimate output if not provided
        if estimated_output_tokens is None:
            estimated_output_tokens = self._estimate_output_tokens(
                input_tokens, classification.task_type
            )

        # Determine minimum quality tier from complexity
        min_quality = self._complexity_to_quality(classification.complexity_score)

        # Get required capability
        required_capability = self.TASK_CAPABILITIES.get(classification.task_type)

        # Evaluate all models
        recommendations = []
        for model in self.model_db.list_models():
            rec = self._evaluate_model(
                model=model,
                classification=classification,
                input_tokens=input_tokens,
                output_tokens=estimated_output_tokens,
                min_quality=min_quality,
                required_capability=required_capability,
            )
            if rec:
                recommendations.append(rec)

        # Sort by score (higher is better: quality/cost ratio)
        recommendations.sort(key=lambda r: r.score, reverse=True)

        # Best choice is highest score that meets requirements
        best = None
        for rec in recommendations:
            if rec.meets_requirements:
                best = rec
                break

        return OptimizationResult(
            recommendations=recommendations[:10],  # Top 10
            best_choice=best,
            task_type=classification.task_type,
            complexity_score=classification.complexity_score,
            input_tokens=input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            quality_requirement=min_quality,
        )

    def _evaluate_model(
        self,
        model: ModelSpec,
        classification: TaskClassification,
        input_tokens: int,
        output_tokens: int,
        min_quality: QualityTier,
        required_capability: Optional[str],
    ) -> Optional[ModelRecommendation]:
        """Evaluate a single model for the task."""
        notes = []
        meets_requirements = True

        # Check capability
        if required_capability and required_capability not in model.capabilities:
            notes.append(f"Missing capability: {required_capability}")
            meets_requirements = False

        # Check quality tier
        model_quality = self.QUALITY_VALUES[model.quality_tier]
        required_quality = self.QUALITY_VALUES[min_quality]
        if model_quality < required_quality:
            notes.append(f"Quality too low: {model.quality_tier.value} < {min_quality.value}")
            meets_requirements = False

        # Check context limit
        total_tokens = input_tokens + output_tokens
        if total_tokens > model.context_limit:
            notes.append(f"Context exceeded: {total_tokens} > {model.context_limit}")
            meets_requirements = False

        # Check requirements
        reqs = classification.requirements
        if reqs.needs_vision and not model.supports_vision:
            notes.append("Vision not supported")
            meets_requirements = False
        if reqs.needs_tools and not model.supports_tools:
            notes.append("Tools not supported")
            meets_requirements = False
        if reqs.streaming_required and not model.supports_streaming:
            notes.append("Streaming not supported")
            meets_requirements = False

        # Speed check for priority tasks
        if reqs.speed_priority:
            if self.SPEED_VALUES[model.speed_tier] < 3:  # Need at least FAST
                notes.append("Not fast enough for priority task")
                # Don't disqualify, just note

        # Calculate costs
        input_cost = (input_tokens / 1_000_000) * model.input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * model.output_price_per_1m
        total_cost = input_cost + output_cost

        # Calculate score: quality / cost (higher is better)
        # Normalize quality to 0-1 range, add speed bonus
        quality_norm = model_quality / 4
        speed_bonus = self.SPEED_VALUES[model.speed_tier] / 4 * 0.2  # 20% weight to speed

        # Avoid division by zero
        cost_factor = max(total_cost, 0.0001)
        score = (quality_norm + speed_bonus) / cost_factor

        # Boost score if meets requirements
        if meets_requirements:
            score *= 1.5

        return ModelRecommendation(
            model_id=model.model_id,
            provider=model.provider.value,
            display_name=model.display_name,
            total_cost=round(total_cost, 6),
            input_cost=round(input_cost, 6),
            output_cost=round(output_cost, 6),
            quality_tier=model.quality_tier.value,
            speed_tier=model.speed_tier.value,
            context_limit=model.context_limit,
            meets_requirements=meets_requirements,
            score=round(score, 4),
            notes=notes,
        )

    def _complexity_to_quality(self, score: float) -> QualityTier:
        """Map complexity score to minimum quality tier."""
        if score >= 8:
            return QualityTier.HIGHEST
        elif score >= 6:
            return QualityTier.HIGH
        elif score >= 3:
            return QualityTier.MEDIUM
        return QualityTier.LOW

    def _estimate_output_tokens(self, input_tokens: int, task_type: TaskType) -> int:
        """Estimate output tokens based on task type."""
        ratios = {
            TaskType.CODE: 1.5,
            TaskType.CREATIVE: 2.0,
            TaskType.REASONING: 1.2,
            TaskType.TRANSLATION: 1.1,
            TaskType.MULTIMODAL: 0.5,
            TaskType.GENERAL: 1.0,
        }
        ratio = ratios.get(task_type, 1.0)
        return int(input_tokens * ratio)

    def get_cost_comparison(
        self,
        input_tokens: int,
        output_tokens: int,
        model_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Compare costs across models."""
        models = (
            [self.model_db.get_model(m) for m in model_ids if self.model_db.get_model(m)]
            if model_ids
            else self.model_db.list_models()
        )

        comparisons = []
        for model in models:
            if model is None:
                continue
            cost = self.model_db.calculate_cost(
                model.model_id, input_tokens, output_tokens
            )
            comparisons.append({
                "model_id": model.model_id,
                "display_name": model.display_name,
                "provider": model.provider.value,
                "total_cost": cost,
                "quality": model.quality_tier.value,
                "speed": model.speed_tier.value,
            })

        return sorted(comparisons, key=lambda c: c["total_cost"] or float("inf"))


def optimize_for_task(
    prompt: str,
    input_tokens: Optional[int] = None,
) -> OptimizationResult:
    """Convenience function: classify and optimize in one call."""
    from .task_classifier import classify_task

    classification = classify_task(prompt)

    # Estimate tokens if not provided (rough: 4 chars per token)
    if input_tokens is None:
        input_tokens = len(prompt) // 4

    optimizer = CostOptimizer()
    return optimizer.optimize(classification, input_tokens)
