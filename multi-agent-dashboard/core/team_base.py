"""Base team class for multi-agent dashboard system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type
from datetime import datetime
import asyncio

from .agent_base import BaseAgent, AgentConfig, AgentRole, AgentStatus, TaskResult
from .voting import VotingMechanism, VoteResult, VotingStrategy


class TeamStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass
class TeamConfig:
    team_id: str
    name: str
    description: str
    voting_strategy: VotingStrategy = VotingStrategy.WEIGHTED
    quorum_threshold: float = 0.6
    vote_timeout_seconds: int = 30
    max_agents: int = 5
    required_roles: List[AgentRole] = field(default_factory=lambda: [AgentRole.LEAD])


@dataclass
class TeamMetrics:
    tasks_completed: int = 0
    tasks_failed: int = 0
    votes_conducted: int = 0
    consensus_rate: float = 1.0
    avg_task_duration_ms: int = 0
    uptime_seconds: float = 0


class BaseTeam:
    """Base class for agent teams."""

    TEAM_ID: str = "T00"
    TEAM_NAME: str = "Base Team"
    DESCRIPTION: str = "Base team implementation"

    def __init__(self, config: TeamConfig):
        self.config = config
        self.team_id = config.team_id
        self.name = config.name
        self.agents: Dict[str, BaseAgent] = {}
        self.voting = VotingMechanism(
            strategy=config.voting_strategy,
            quorum_threshold=config.quorum_threshold,
            timeout_seconds=config.vote_timeout_seconds,
        )
        self.metrics = TeamMetrics()
        self._created_at = datetime.utcnow()
        self._task_queue: asyncio.Queue = asyncio.Queue()

    @property
    def status(self) -> TeamStatus:
        """Calculate team health status."""
        if not self.agents:
            return TeamStatus.OFFLINE

        online_count = sum(
            1 for a in self.agents.values() if a.status != AgentStatus.OFFLINE
        )
        total = len(self.agents)

        if online_count == 0:
            return TeamStatus.OFFLINE
        elif online_count < total * 0.5:
            return TeamStatus.CRITICAL
        elif online_count < total:
            return TeamStatus.DEGRADED
        return TeamStatus.HEALTHY

    @property
    def lead(self) -> Optional[BaseAgent]:
        """Get team lead agent."""
        for agent in self.agents.values():
            if agent.role == AgentRole.LEAD:
                return agent
        return None

    def add_agent(self, agent: BaseAgent) -> bool:
        """Add an agent to the team."""
        if len(self.agents) >= self.config.max_agents:
            return False
        if agent.agent_id in self.agents:
            return False
        self.agents[agent.agent_id] = agent
        return True

    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the team."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            return True
        return False

    async def assign_task(self, task: Dict[str, Any]) -> Optional[str]:
        """Assign a task to an available agent."""
        available = [a for a in self.agents.values() if a.can_accept_task()]
        if not available:
            await self._task_queue.put(task)
            return None

        # Prefer lead for complex tasks, workers for simple
        complexity = task.get("complexity", 5)
        if complexity >= 7:
            agent = self.lead or available[0]
        else:
            workers = [a for a in available if a.role == AgentRole.WORKER]
            agent = workers[0] if workers else available[0]

        asyncio.create_task(self._execute_task_with_agent(agent, task))
        return agent.agent_id

    async def _execute_task_with_agent(
        self, agent: BaseAgent, task: Dict[str, Any]
    ) -> TaskResult:
        """Execute task and update metrics."""
        result = await agent.execute_task(task)
        self._update_metrics(result)
        return result

    def _update_metrics(self, result: TaskResult) -> None:
        """Update team metrics after task completion."""
        if result.success:
            self.metrics.tasks_completed += 1
        else:
            self.metrics.tasks_failed += 1

        # Rolling average for duration
        total = self.metrics.tasks_completed + self.metrics.tasks_failed
        self.metrics.avg_task_duration_ms = int(
            (self.metrics.avg_task_duration_ms * (total - 1) + result.duration_ms)
            / total
        )

    async def vote(
        self,
        topic: str,
        options: List[str],
        context: Optional[Dict[str, Any]] = None,
        strategy: Optional[VotingStrategy] = None,
    ) -> VoteResult:
        """Conduct a vote among team members."""
        context = context or {}
        voters = list(self.agents.values())

        result = await self.voting.conduct_vote(
            topic=topic,
            options=options,
            voters=voters,
            context=context,
            strategy=strategy,
        )

        self.metrics.votes_conducted += 1
        if result.consensus_reached:
            # Update rolling consensus rate
            rate = self.metrics.consensus_rate
            self.metrics.consensus_rate = (
                rate * (self.metrics.votes_conducted - 1) + 1.0
            ) / self.metrics.votes_conducted
        else:
            rate = self.metrics.consensus_rate
            self.metrics.consensus_rate = (
                rate * (self.metrics.votes_conducted - 1)
            ) / self.metrics.votes_conducted

        return result

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all agents."""
        tasks = [agent.receive_message(message) for agent in self.agents.values()]
        await asyncio.gather(*tasks)

    def get_status(self) -> Dict[str, Any]:
        """Get team status summary."""
        self.metrics.uptime_seconds = (
            datetime.utcnow() - self._created_at
        ).total_seconds()

        return {
            "team_id": self.team_id,
            "name": self.name,
            "status": self.status.value,
            "agent_count": len(self.agents),
            "agents": [a.get_status() for a in self.agents.values()],
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "votes_conducted": self.metrics.votes_conducted,
                "consensus_rate": round(self.metrics.consensus_rate, 3),
                "avg_task_duration_ms": self.metrics.avg_task_duration_ms,
                "uptime_seconds": int(self.metrics.uptime_seconds),
            },
            "voting_strategy": self.config.voting_strategy.value,
            "quorum_threshold": self.config.quorum_threshold,
        }

    def __repr__(self) -> str:
        return f"<Team {self.name} ({len(self.agents)} agents) - {self.status.value}>"


def create_team_with_agents(
    team_config: TeamConfig,
    agent_configs: List[AgentConfig],
    agent_class: Type[BaseAgent],
) -> BaseTeam:
    """Factory function to create a team with agents."""
    team = BaseTeam(team_config)
    for config in agent_configs:
        config.team_id = team.team_id
        agent = agent_class(config)
        team.add_agent(agent)
    return team
