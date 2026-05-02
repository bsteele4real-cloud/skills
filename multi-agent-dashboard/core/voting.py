"""Voting and consensus mechanisms for multi-agent system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
import asyncio
from collections import Counter

if TYPE_CHECKING:
    from .agent_base import BaseAgent


class VotingStrategy(Enum):
    MAJORITY = "majority"
    SUPERMAJORITY = "supermajority"
    WEIGHTED = "weighted"
    QUORUM = "quorum"
    UNANIMOUS = "unanimous"
    RANKED = "ranked"


@dataclass
class Vote:
    agent_id: str
    agent_name: str
    choice: str
    weight: float
    reasoning: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0


@dataclass
class VoteResult:
    topic: str
    winner: Optional[str]
    votes: List[Vote]
    strategy: VotingStrategy
    consensus_reached: bool
    confidence: float
    vote_counts: Dict[str, float]
    participation_rate: float
    duration_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class VotingMechanism:
    """Implements various voting strategies for agent consensus."""

    def __init__(
        self,
        strategy: VotingStrategy = VotingStrategy.WEIGHTED,
        quorum_threshold: float = 0.6,
        timeout_seconds: int = 30,
    ):
        self.strategy = strategy
        self.quorum_threshold = quorum_threshold
        self.timeout_seconds = timeout_seconds

    async def conduct_vote(
        self,
        topic: str,
        options: List[str],
        voters: List["BaseAgent"],
        context: Optional[Dict[str, Any]] = None,
        strategy: Optional[VotingStrategy] = None,
    ) -> VoteResult:
        """Conduct a vote among agents."""
        strategy = strategy or self.strategy
        context = context or {}
        start_time = datetime.utcnow()

        # Collect votes with timeout
        votes = await self._collect_votes(topic, options, voters, context)

        # Calculate participation
        participation_rate = len(votes) / len(voters) if voters else 0

        # Check quorum
        if participation_rate < self.quorum_threshold:
            return VoteResult(
                topic=topic,
                winner=None,
                votes=votes,
                strategy=strategy,
                consensus_reached=False,
                confidence=0.0,
                vote_counts={},
                participation_rate=participation_rate,
                duration_ms=self._calc_duration(start_time),
                metadata={"error": "quorum_not_met"},
            )

        # Apply voting strategy
        result = self._apply_strategy(topic, votes, options, strategy)
        result.participation_rate = participation_rate
        result.duration_ms = self._calc_duration(start_time)

        return result

    async def _collect_votes(
        self,
        topic: str,
        options: List[str],
        voters: List["BaseAgent"],
        context: Dict[str, Any],
    ) -> List[Vote]:
        """Collect votes from all agents with timeout."""
        votes = []

        async def get_vote(agent: "BaseAgent") -> Optional[Vote]:
            try:
                choice = await asyncio.wait_for(
                    agent.vote(topic, options, context),
                    timeout=self.timeout_seconds,
                )
                return Vote(
                    agent_id=agent.agent_id,
                    agent_name=agent.name,
                    choice=choice,
                    weight=agent.vote_weight,
                )
            except asyncio.TimeoutError:
                return None
            except Exception:
                return None

        results = await asyncio.gather(*[get_vote(v) for v in voters])
        votes = [v for v in results if v is not None]

        return votes

    def _apply_strategy(
        self,
        topic: str,
        votes: List[Vote],
        options: List[str],
        strategy: VotingStrategy,
    ) -> VoteResult:
        """Apply the specified voting strategy."""
        if strategy == VotingStrategy.MAJORITY:
            return self._majority_vote(topic, votes, options, strategy)
        elif strategy == VotingStrategy.SUPERMAJORITY:
            return self._supermajority_vote(topic, votes, options, strategy)
        elif strategy == VotingStrategy.WEIGHTED:
            return self._weighted_vote(topic, votes, options, strategy)
        elif strategy == VotingStrategy.UNANIMOUS:
            return self._unanimous_vote(topic, votes, options, strategy)
        elif strategy == VotingStrategy.RANKED:
            return self._ranked_vote(topic, votes, options, strategy)
        else:
            return self._majority_vote(topic, votes, options, strategy)

    def _majority_vote(
        self,
        topic: str,
        votes: List[Vote],
        options: List[str],
        strategy: VotingStrategy,
    ) -> VoteResult:
        """Simple majority (>50%) wins."""
        counts = Counter(v.choice for v in votes)
        total = len(votes)

        if not total:
            return self._no_winner_result(topic, votes, strategy, options)

        winner, winner_count = counts.most_common(1)[0]
        consensus = winner_count > total / 2
        confidence = winner_count / total if total else 0

        return VoteResult(
            topic=topic,
            winner=winner if consensus else None,
            votes=votes,
            strategy=strategy,
            consensus_reached=consensus,
            confidence=confidence,
            vote_counts={opt: counts.get(opt, 0) for opt in options},
            participation_rate=0,
            duration_ms=0,
        )

    def _supermajority_vote(
        self,
        topic: str,
        votes: List[Vote],
        options: List[str],
        strategy: VotingStrategy,
    ) -> VoteResult:
        """2/3 supermajority required."""
        counts = Counter(v.choice for v in votes)
        total = len(votes)

        if not total:
            return self._no_winner_result(topic, votes, strategy, options)

        winner, winner_count = counts.most_common(1)[0]
        consensus = winner_count >= (total * 2 / 3)
        confidence = winner_count / total if total else 0

        return VoteResult(
            topic=topic,
            winner=winner if consensus else None,
            votes=votes,
            strategy=strategy,
            consensus_reached=consensus,
            confidence=confidence,
            vote_counts={opt: counts.get(opt, 0) for opt in options},
            participation_rate=0,
            duration_ms=0,
        )

    def _weighted_vote(
        self,
        topic: str,
        votes: List[Vote],
        options: List[str],
        strategy: VotingStrategy,
    ) -> VoteResult:
        """Weighted voting based on agent roles."""
        weighted_counts: Dict[str, float] = {opt: 0 for opt in options}
        total_weight = sum(v.weight for v in votes)

        for vote in votes:
            if vote.choice in weighted_counts:
                weighted_counts[vote.choice] += vote.weight

        if not total_weight:
            return self._no_winner_result(topic, votes, strategy, options)

        winner = max(weighted_counts, key=lambda k: weighted_counts[k])
        winner_weight = weighted_counts[winner]
        consensus = winner_weight > total_weight / 2
        confidence = winner_weight / total_weight

        return VoteResult(
            topic=topic,
            winner=winner if consensus else None,
            votes=votes,
            strategy=strategy,
            consensus_reached=consensus,
            confidence=confidence,
            vote_counts=weighted_counts,
            participation_rate=0,
            duration_ms=0,
        )

    def _unanimous_vote(
        self,
        topic: str,
        votes: List[Vote],
        options: List[str],
        strategy: VotingStrategy,
    ) -> VoteResult:
        """All must agree (for security decisions)."""
        if not votes:
            return self._no_winner_result(topic, votes, strategy, options)

        choices = set(v.choice for v in votes)
        consensus = len(choices) == 1
        winner = votes[0].choice if consensus else None

        counts = Counter(v.choice for v in votes)

        return VoteResult(
            topic=topic,
            winner=winner,
            votes=votes,
            strategy=strategy,
            consensus_reached=consensus,
            confidence=1.0 if consensus else 0.0,
            vote_counts={opt: counts.get(opt, 0) for opt in options},
            participation_rate=0,
            duration_ms=0,
        )

    def _ranked_vote(
        self,
        topic: str,
        votes: List[Vote],
        options: List[str],
        strategy: VotingStrategy,
    ) -> VoteResult:
        """Ranked choice / instant runoff voting."""
        # For simplicity, treat choice as first preference
        # Full ranked choice would need preference ordering
        return self._majority_vote(topic, votes, options, strategy)

    def _no_winner_result(
        self,
        topic: str,
        votes: List[Vote],
        strategy: VotingStrategy,
        options: List[str],
    ) -> VoteResult:
        """Return result when no winner determined."""
        return VoteResult(
            topic=topic,
            winner=None,
            votes=votes,
            strategy=strategy,
            consensus_reached=False,
            confidence=0.0,
            vote_counts={opt: 0 for opt in options},
            participation_rate=0,
            duration_ms=0,
        )

    def _calc_duration(self, start: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.utcnow() - start).total_seconds() * 1000)


# Convenience function for quick votes
async def quick_vote(
    topic: str,
    options: List[str],
    voters: List["BaseAgent"],
    strategy: VotingStrategy = VotingStrategy.MAJORITY,
) -> VoteResult:
    """Quick voting helper."""
    mechanism = VotingMechanism(strategy=strategy)
    return await mechanism.conduct_vote(topic, options, voters)
