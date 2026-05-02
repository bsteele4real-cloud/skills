"""Live model database with capabilities and pricing."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio


class Provider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    XAI = "xai"
    MISTRAL = "mistral"
    COHERE = "cohere"
    META = "meta"


class QualityTier(Enum):
    HIGHEST = "highest"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SpeedTier(Enum):
    VERY_FAST = "very_fast"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


@dataclass
class ModelSpec:
    model_id: str
    provider: Provider
    display_name: str
    context_limit: int
    input_price_per_1m: float  # USD per 1M tokens
    output_price_per_1m: float
    capabilities: List[str]
    quality_tier: QualityTier
    speed_tier: SpeedTier
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True
    max_output_tokens: int = 8192
    last_updated: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelDatabase:
    """Real-time model capabilities and pricing database."""

    def __init__(self):
        self._models: Dict[str, ModelSpec] = {}
        self._load_default_models()
        self._last_refresh: Optional[datetime] = None

    def _load_default_models(self) -> None:
        """Load default model specifications."""
        models = [
            # OpenAI
            ModelSpec(
                model_id="gpt-4o",
                provider=Provider.OPENAI,
                display_name="GPT-4o",
                context_limit=128000,
                input_price_per_1m=2.50,
                output_price_per_1m=10.00,
                capabilities=["code", "creative", "reasoning", "vision"],
                quality_tier=QualityTier.HIGH,
                speed_tier=SpeedTier.FAST,
                supports_vision=True,
                max_output_tokens=16384,
            ),
            ModelSpec(
                model_id="gpt-4o-mini",
                provider=Provider.OPENAI,
                display_name="GPT-4o Mini",
                context_limit=128000,
                input_price_per_1m=0.15,
                output_price_per_1m=0.60,
                capabilities=["code", "creative", "reasoning", "vision"],
                quality_tier=QualityTier.MEDIUM,
                speed_tier=SpeedTier.VERY_FAST,
                supports_vision=True,
                max_output_tokens=16384,
            ),
            ModelSpec(
                model_id="o1",
                provider=Provider.OPENAI,
                display_name="o1",
                context_limit=200000,
                input_price_per_1m=15.00,
                output_price_per_1m=60.00,
                capabilities=["code", "reasoning", "math"],
                quality_tier=QualityTier.HIGHEST,
                speed_tier=SpeedTier.SLOW,
                supports_tools=False,
                supports_streaming=False,
                max_output_tokens=100000,
            ),
            ModelSpec(
                model_id="o3-mini",
                provider=Provider.OPENAI,
                display_name="o3-mini",
                context_limit=200000,
                input_price_per_1m=1.10,
                output_price_per_1m=4.40,
                capabilities=["code", "reasoning", "math"],
                quality_tier=QualityTier.HIGH,
                speed_tier=SpeedTier.FAST,
                supports_tools=False,
                supports_streaming=False,
                max_output_tokens=100000,
            ),
            # Anthropic
            ModelSpec(
                model_id="claude-opus-4",
                provider=Provider.ANTHROPIC,
                display_name="Claude Opus 4",
                context_limit=200000,
                input_price_per_1m=15.00,
                output_price_per_1m=75.00,
                capabilities=["code", "creative", "reasoning", "vision"],
                quality_tier=QualityTier.HIGHEST,
                speed_tier=SpeedTier.MEDIUM,
                supports_vision=True,
                max_output_tokens=32000,
            ),
            ModelSpec(
                model_id="claude-sonnet-4",
                provider=Provider.ANTHROPIC,
                display_name="Claude Sonnet 4",
                context_limit=200000,
                input_price_per_1m=3.00,
                output_price_per_1m=15.00,
                capabilities=["code", "creative", "reasoning", "vision"],
                quality_tier=QualityTier.HIGH,
                speed_tier=SpeedTier.FAST,
                supports_vision=True,
                max_output_tokens=64000,
            ),
            ModelSpec(
                model_id="claude-haiku-4",
                provider=Provider.ANTHROPIC,
                display_name="Claude Haiku 4",
                context_limit=200000,
                input_price_per_1m=0.80,
                output_price_per_1m=4.00,
                capabilities=["code", "creative", "reasoning"],
                quality_tier=QualityTier.MEDIUM,
                speed_tier=SpeedTier.VERY_FAST,
                max_output_tokens=8192,
            ),
            # Google
            ModelSpec(
                model_id="gemini-2.0-flash",
                provider=Provider.GOOGLE,
                display_name="Gemini 2.0 Flash",
                context_limit=1000000,
                input_price_per_1m=0.10,
                output_price_per_1m=0.40,
                capabilities=["code", "creative", "reasoning", "vision", "multimodal"],
                quality_tier=QualityTier.MEDIUM,
                speed_tier=SpeedTier.VERY_FAST,
                supports_vision=True,
                max_output_tokens=8192,
            ),
            ModelSpec(
                model_id="gemini-2.5-pro",
                provider=Provider.GOOGLE,
                display_name="Gemini 2.5 Pro",
                context_limit=1000000,
                input_price_per_1m=1.25,
                output_price_per_1m=10.00,
                capabilities=["code", "creative", "reasoning", "vision", "multimodal"],
                quality_tier=QualityTier.HIGH,
                speed_tier=SpeedTier.FAST,
                supports_vision=True,
                max_output_tokens=65536,
            ),
            # xAI
            ModelSpec(
                model_id="grok-3",
                provider=Provider.XAI,
                display_name="Grok 3",
                context_limit=131072,
                input_price_per_1m=3.00,
                output_price_per_1m=15.00,
                capabilities=["code", "creative", "reasoning", "vision"],
                quality_tier=QualityTier.HIGH,
                speed_tier=SpeedTier.FAST,
                supports_vision=True,
                max_output_tokens=16384,
            ),
            ModelSpec(
                model_id="grok-3-mini",
                provider=Provider.XAI,
                display_name="Grok 3 Mini",
                context_limit=131072,
                input_price_per_1m=0.30,
                output_price_per_1m=0.50,
                capabilities=["code", "creative", "reasoning"],
                quality_tier=QualityTier.MEDIUM,
                speed_tier=SpeedTier.VERY_FAST,
                max_output_tokens=16384,
            ),
            # Mistral
            ModelSpec(
                model_id="mistral-large",
                provider=Provider.MISTRAL,
                display_name="Mistral Large",
                context_limit=128000,
                input_price_per_1m=2.00,
                output_price_per_1m=6.00,
                capabilities=["code", "creative", "reasoning"],
                quality_tier=QualityTier.HIGH,
                speed_tier=SpeedTier.FAST,
                max_output_tokens=8192,
            ),
            ModelSpec(
                model_id="mistral-small",
                provider=Provider.MISTRAL,
                display_name="Mistral Small",
                context_limit=32000,
                input_price_per_1m=0.10,
                output_price_per_1m=0.30,
                capabilities=["code", "creative", "reasoning"],
                quality_tier=QualityTier.MEDIUM,
                speed_tier=SpeedTier.VERY_FAST,
                max_output_tokens=8192,
            ),
        ]

        for model in models:
            self._models[model.model_id] = model

    def get_model(self, model_id: str) -> Optional[ModelSpec]:
        """Get a specific model specification."""
        return self._models.get(model_id)

    def list_models(
        self,
        provider: Optional[Provider] = None,
        quality_tier: Optional[QualityTier] = None,
        capability: Optional[str] = None,
    ) -> List[ModelSpec]:
        """List models matching criteria."""
        models = list(self._models.values())

        if provider:
            models = [m for m in models if m.provider == provider]
        if quality_tier:
            models = [m for m in models if m.quality_tier == quality_tier]
        if capability:
            models = [m for m in models if capability in m.capabilities]

        return models

    def get_models_by_capability(self, capability: str) -> List[ModelSpec]:
        """Get all models with a specific capability."""
        return [m for m in self._models.values() if capability in m.capabilities]

    def get_cheapest_model(
        self,
        capability: Optional[str] = None,
        min_quality: QualityTier = QualityTier.LOW,
    ) -> Optional[ModelSpec]:
        """Get the cheapest model meeting requirements."""
        quality_order = [QualityTier.LOW, QualityTier.MEDIUM, QualityTier.HIGH, QualityTier.HIGHEST]
        min_quality_idx = quality_order.index(min_quality)

        candidates = []
        for model in self._models.values():
            model_quality_idx = quality_order.index(model.quality_tier)
            if model_quality_idx < min_quality_idx:
                continue
            if capability and capability not in model.capabilities:
                continue
            candidates.append(model)

        if not candidates:
            return None

        # Sort by average cost (input + output) / 2
        return min(
            candidates,
            key=lambda m: (m.input_price_per_1m + m.output_price_per_1m) / 2
        )

    def calculate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Optional[float]:
        """Calculate cost for a specific model and token counts."""
        model = self._models.get(model_id)
        if not model:
            return None

        input_cost = (input_tokens / 1_000_000) * model.input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * model.output_price_per_1m

        return round(input_cost + output_cost, 6)

    async def refresh_prices(self) -> None:
        """Refresh prices from provider APIs (placeholder)."""
        # In production, this would call provider APIs
        # For now, just update timestamp
        self._last_refresh = datetime.utcnow()

    def update_model(
        self,
        model_id: str,
        input_price: Optional[float] = None,
        output_price: Optional[float] = None,
        context_limit: Optional[int] = None,
    ) -> bool:
        """Update model specifications."""
        if model_id not in self._models:
            return False

        model = self._models[model_id]
        if input_price is not None:
            model.input_price_per_1m = input_price
        if output_price is not None:
            model.output_price_per_1m = output_price
        if context_limit is not None:
            model.context_limit = context_limit
        model.last_updated = datetime.utcnow()

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        by_provider = {}
        by_quality = {}

        for model in self._models.values():
            provider = model.provider.value
            by_provider[provider] = by_provider.get(provider, 0) + 1

            quality = model.quality_tier.value
            by_quality[quality] = by_quality.get(quality, 0) + 1

        return {
            "total_models": len(self._models),
            "by_provider": by_provider,
            "by_quality": by_quality,
            "last_refresh": (
                self._last_refresh.isoformat() if self._last_refresh else None
            ),
        }


# Global database instance
_db: Optional[ModelDatabase] = None


def get_model_database() -> ModelDatabase:
    """Get or create the global model database."""
    global _db
    if _db is None:
        _db = ModelDatabase()
    return _db
