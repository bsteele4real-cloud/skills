"""Task classification and complexity scoring for optimal model routing."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import re
import math


class TaskType(Enum):
    CODE = "code"
    CREATIVE = "creative"
    REASONING = "reasoning"
    TRANSLATION = "translation"
    MULTIMODAL = "multimodal"
    GENERAL = "general"


@dataclass
class Requirements:
    min_context_length: int = 4096
    needs_tools: bool = False
    needs_vision: bool = False
    needs_code_execution: bool = False
    speed_priority: bool = False
    streaming_required: bool = False


@dataclass
class TaskClassification:
    task_type: TaskType
    complexity_score: float  # 0-10
    requirements: Requirements
    feature_vector: List[float]
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskClassifier:
    """NLP-based task classification and complexity scoring."""

    # Keywords for task type detection
    TASK_KEYWORDS = {
        TaskType.CODE: [
            "code", "function", "class", "implement", "debug", "fix", "error",
            "python", "javascript", "typescript", "rust", "java", "sql",
            "api", "endpoint", "database", "query", "algorithm", "refactor",
            "test", "unit test", "compile", "syntax", "variable", "loop",
        ],
        TaskType.CREATIVE: [
            "write", "story", "poem", "creative", "imagine", "describe",
            "narrative", "fiction", "character", "plot", "dialogue",
            "blog", "article", "essay", "content", "marketing copy",
            "slogan", "tagline", "brainstorm", "ideas",
        ],
        TaskType.REASONING: [
            "analyze", "explain", "why", "how", "compare", "evaluate",
            "reason", "logic", "argument", "conclusion", "evidence",
            "pros and cons", "decision", "strategy", "plan", "solve",
            "calculate", "math", "proof", "derive",
        ],
        TaskType.TRANSLATION: [
            "translate", "translation", "convert", "language",
            "spanish", "french", "german", "chinese", "japanese",
            "localize", "localization", "multilingual",
        ],
        TaskType.MULTIMODAL: [
            "image", "picture", "photo", "video", "audio", "visual",
            "diagram", "chart", "graph", "screenshot", "describe this",
            "what do you see", "analyze this image",
        ],
    }

    # Domain-specific vocabulary for depth scoring
    DOMAIN_VOCAB = {
        "technical": [
            "kubernetes", "microservices", "distributed", "consensus",
            "cryptography", "encryption", "protocol", "architecture",
            "scalability", "latency", "throughput", "optimization",
        ],
        "scientific": [
            "hypothesis", "methodology", "empirical", "statistical",
            "correlation", "causation", "experiment", "control group",
            "peer review", "replication", "significance",
        ],
        "legal": [
            "jurisdiction", "liability", "compliance", "regulation",
            "statute", "precedent", "contract", "indemnification",
        ],
        "medical": [
            "diagnosis", "prognosis", "treatment", "symptom",
            "contraindication", "dosage", "clinical", "pathology",
        ],
        "financial": [
            "derivatives", "hedging", "arbitrage", "portfolio",
            "valuation", "liquidity", "leverage", "amortization",
        ],
    }

    # Chain-of-thought indicators
    COT_INDICATORS = [
        "step by step", "first", "then", "next", "finally",
        "let's think", "break down", "analyze each", "consider",
        "reasoning:", "steps:", "process:", "1.", "2.", "3.",
    ]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self._task_patterns = {
            task_type: re.compile(
                r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b',
                re.IGNORECASE
            )
            for task_type, keywords in self.TASK_KEYWORDS.items()
        }

        self._domain_patterns = {
            domain: re.compile(
                r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b',
                re.IGNORECASE
            )
            for domain, keywords in self.DOMAIN_VOCAB.items()
        }

        self._cot_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(ind) for ind in self.COT_INDICATORS) + r')\b',
            re.IGNORECASE
        )

    def classify(self, prompt: str) -> TaskClassification:
        """Classify prompt and score complexity."""
        task_type, type_confidence = self._classify_type(prompt)
        complexity = self._score_complexity(prompt)
        requirements = self._detect_requirements(prompt)
        feature_vector = self._build_feature_vector(
            task_type, complexity, requirements
        )

        return TaskClassification(
            task_type=task_type,
            complexity_score=complexity,
            requirements=requirements,
            feature_vector=feature_vector,
            confidence=type_confidence,
            metadata={
                "prompt_length": len(prompt),
                "word_count": len(prompt.split()),
            },
        )

    def _classify_type(self, prompt: str) -> Tuple[TaskType, float]:
        """Classify the task type with confidence."""
        scores: Dict[TaskType, int] = {}

        for task_type, pattern in self._task_patterns.items():
            matches = pattern.findall(prompt)
            scores[task_type] = len(matches)

        if not any(scores.values()):
            return TaskType.GENERAL, 0.5

        best_type = max(scores, key=lambda t: scores[t])
        total_matches = sum(scores.values())
        confidence = scores[best_type] / total_matches if total_matches else 0.5

        return best_type, min(confidence, 1.0)

    def _score_complexity(self, prompt: str) -> float:
        """Multi-factor complexity scoring 0-10."""
        # Factor 1: Steps (Chain-of-Thought indicators)
        cot_matches = self._cot_pattern.findall(prompt)
        step_score = min(len(cot_matches) / 5, 1.0) * 2.5

        # Factor 2: Ambiguity (question words, uncertainty)
        ambiguity = self._measure_ambiguity(prompt)
        ambiguity_score = ambiguity * 2.5

        # Factor 3: Domain depth (expert vocabulary)
        domain_depth = self._measure_domain_depth(prompt)
        domain_score = domain_depth * 2.5

        # Factor 4: Length factor
        word_count = len(prompt.split())
        length_score = min(word_count / 500, 1.0) * 2.5

        total = step_score + ambiguity_score + domain_score + length_score
        return round(min(total, 10.0), 2)

    def _measure_ambiguity(self, prompt: str) -> float:
        """Measure prompt ambiguity (0-1)."""
        ambiguity_indicators = [
            "maybe", "perhaps", "might", "could", "possibly",
            "what if", "how about", "consider", "various", "multiple",
            "?", "or", "either", "alternative",
        ]

        prompt_lower = prompt.lower()
        matches = sum(1 for ind in ambiguity_indicators if ind in prompt_lower)

        # Normalize
        return min(matches / 5, 1.0)

    def _measure_domain_depth(self, prompt: str) -> float:
        """Measure domain-specific vocabulary usage (0-1)."""
        total_matches = 0

        for pattern in self._domain_patterns.values():
            matches = pattern.findall(prompt)
            total_matches += len(matches)

        # Normalize
        return min(total_matches / 10, 1.0)

    def _detect_requirements(self, prompt: str) -> Requirements:
        """Detect model requirements from prompt."""
        prompt_lower = prompt.lower()
        word_count = len(prompt.split())

        # Context length estimation (rough heuristic)
        estimated_context = word_count * 2 + 1000  # Input + expected output

        return Requirements(
            min_context_length=max(4096, estimated_context),
            needs_tools=(
                "function" in prompt_lower
                or "api" in prompt_lower
                or "call" in prompt_lower
                or "execute" in prompt_lower
            ),
            needs_vision=(
                "image" in prompt_lower
                or "picture" in prompt_lower
                or "photo" in prompt_lower
                or "screenshot" in prompt_lower
                or "diagram" in prompt_lower
            ),
            needs_code_execution=(
                "run" in prompt_lower
                or "execute" in prompt_lower
                or "output" in prompt_lower
            ),
            speed_priority=(
                "quick" in prompt_lower
                or "fast" in prompt_lower
                or "urgent" in prompt_lower
                or "asap" in prompt_lower
            ),
            streaming_required=(
                "stream" in prompt_lower
                or "real-time" in prompt_lower
            ),
        )

    def _build_feature_vector(
        self,
        task_type: TaskType,
        complexity: float,
        requirements: Requirements,
    ) -> List[float]:
        """Build feature vector for optimizer matching."""
        # Task type one-hot (6 types)
        type_vector = [0.0] * 6
        type_index = list(TaskType).index(task_type)
        type_vector[type_index] = 1.0

        # Complexity normalized
        complexity_norm = complexity / 10.0

        # Requirements as binary features
        req_vector = [
            1.0 if requirements.needs_tools else 0.0,
            1.0 if requirements.needs_vision else 0.0,
            1.0 if requirements.needs_code_execution else 0.0,
            1.0 if requirements.speed_priority else 0.0,
            1.0 if requirements.streaming_required else 0.0,
            requirements.min_context_length / 200000,  # Normalized to max context
        ]

        return type_vector + [complexity_norm] + req_vector


def classify_task(prompt: str) -> TaskClassification:
    """Convenience function for quick classification."""
    classifier = TaskClassifier()
    return classifier.classify(prompt)
