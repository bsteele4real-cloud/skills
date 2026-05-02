"""Token counting and estimation for different model families."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import re


@dataclass
class TokenCount:
    count: int
    provider: str
    method: str  # "exact" or "estimated"


class TokenEstimator:
    """Accurate token counting per model family."""

    # Average characters per token by provider (approximations)
    CHARS_PER_TOKEN = {
        "openai": 4.0,
        "anthropic": 4.0,
        "google": 4.0,
        "xai": 4.0,
        "mistral": 4.0,
        "default": 4.0,
    }

    # Output ratios by task type
    OUTPUT_RATIOS = {
        "code": 1.5,
        "creative": 2.0,
        "reasoning": 1.2,
        "translation": 1.1,
        "multimodal": 0.5,
        "general": 1.0,
    }

    def __init__(self):
        self._tiktoken_available = self._check_tiktoken()

    def _check_tiktoken(self) -> bool:
        """Check if tiktoken is available."""
        try:
            import tiktoken
            return True
        except ImportError:
            return False

    def count_tokens(
        self,
        text: str,
        provider: str = "default",
    ) -> TokenCount:
        """Count tokens for text."""
        if self._tiktoken_available and provider in ["openai", "anthropic"]:
            return self._count_with_tiktoken(text, provider)
        return self._estimate_tokens(text, provider)

    def _count_with_tiktoken(self, text: str, provider: str) -> TokenCount:
        """Count tokens using tiktoken (accurate for OpenAI/Anthropic)."""
        try:
            import tiktoken

            # cl100k_base is used by GPT-4 and Claude
            encoding = tiktoken.get_encoding("cl100k_base")
            tokens = encoding.encode(text)

            return TokenCount(
                count=len(tokens),
                provider=provider,
                method="exact",
            )
        except Exception:
            return self._estimate_tokens(text, provider)

    def _estimate_tokens(self, text: str, provider: str) -> TokenCount:
        """Estimate tokens using character ratio."""
        chars_per_token = self.CHARS_PER_TOKEN.get(
            provider, self.CHARS_PER_TOKEN["default"]
        )

        # Basic estimation
        estimated = len(text) / chars_per_token

        # Adjust for special patterns
        # URLs and code tend to tokenize more efficiently
        url_count = len(re.findall(r'https?://\S+', text))
        code_blocks = len(re.findall(r'```[\s\S]*?```', text))

        # Reduce estimate slightly for these patterns
        adjustment = (url_count * 5 + code_blocks * 10) * 0.1
        estimated = max(1, estimated - adjustment)

        return TokenCount(
            count=int(estimated),
            provider=provider,
            method="estimated",
        )

    def estimate_output_tokens(
        self,
        input_tokens: int,
        task_type: str = "general",
    ) -> int:
        """Estimate output tokens based on task type."""
        ratio = self.OUTPUT_RATIOS.get(task_type, 1.0)
        return int(input_tokens * ratio)

    def count_messages_tokens(
        self,
        messages: List[Dict[str, str]],
        provider: str = "default",
    ) -> TokenCount:
        """Count tokens for a list of messages."""
        total = 0

        for msg in messages:
            # Count role
            role = msg.get("role", "")
            role_tokens = self.count_tokens(role, provider)

            # Count content
            content = msg.get("content", "")
            content_tokens = self.count_tokens(content, provider)

            # Add overhead per message (roughly 4 tokens for formatting)
            total += role_tokens.count + content_tokens.count + 4

        return TokenCount(
            count=total,
            provider=provider,
            method="estimated",
        )

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        input_price_per_1m: float,
        output_price_per_1m: float,
    ) -> Tuple[float, float, float]:
        """Estimate cost for given token counts and prices."""
        input_cost = (input_tokens / 1_000_000) * input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * output_price_per_1m
        total_cost = input_cost + output_cost

        return (
            round(input_cost, 6),
            round(output_cost, 6),
            round(total_cost, 6),
        )

    def get_context_usage(
        self,
        input_tokens: int,
        estimated_output: int,
        context_limit: int,
    ) -> Dict[str, any]:
        """Calculate context window usage."""
        total = input_tokens + estimated_output
        usage_pct = (total / context_limit) * 100 if context_limit else 0
        remaining = max(0, context_limit - total)

        return {
            "input_tokens": input_tokens,
            "estimated_output": estimated_output,
            "total_estimated": total,
            "context_limit": context_limit,
            "usage_percentage": round(usage_pct, 1),
            "remaining_tokens": remaining,
            "fits_context": total <= context_limit,
        }


def count_tokens(text: str, provider: str = "default") -> int:
    """Convenience function for quick token counting."""
    estimator = TokenEstimator()
    return estimator.count_tokens(text, provider).count


def estimate_cost(
    text: str,
    task_type: str = "general",
    input_price: float = 3.0,
    output_price: float = 15.0,
) -> Dict[str, float]:
    """Convenience function to estimate full cost."""
    estimator = TokenEstimator()

    input_result = estimator.count_tokens(text)
    input_tokens = input_result.count
    output_tokens = estimator.estimate_output_tokens(input_tokens, task_type)

    input_cost, output_cost, total = estimator.estimate_cost(
        input_tokens, output_tokens, input_price, output_price
    )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total,
    }
