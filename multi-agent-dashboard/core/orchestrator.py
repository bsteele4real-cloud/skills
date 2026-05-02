"""High-level orchestrator agent that manages all teams."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import asyncio

from .agent_base import BaseAgent, AgentConfig, AgentRole, LLMAgent, TaskResult
from .team_base import BaseTeam, TeamStatus
from .voting import VotingMechanism, VotingStrategy, VoteResult
from .message_bus import MessageBus, get_message_bus, MessageType, MessagePriority


class EscalationLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class WorkflowSuggestion:
    suggestion_id: str
    category: str
    description: str
    impact: str
    effort: str
    affected_teams: List[str]
    priority: int
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OrchestratorState:
    teams: Dict[str, BaseTeam] = field(default_factory=dict)
    pending_escalations: List[Dict[str, Any]] = field(default_factory=list)
    workflow_suggestions: List[WorkflowSuggestion] = field(default_factory=list)
    improvement_cycle_phase: str = "idle"
    last_health_check: Optional[datetime] = None


class Orchestrator:
    """High-level orchestrator managing all teams and workflows."""

    TEAM_IDS = [f"T{i:02d}" for i in range(1, 11)]

    def __init__(self, llm_client: Any = None):
        self.state = OrchestratorState()
        self.message_bus = get_message_bus()
        self.llm_client = llm_client
        self._running = False
        self._health_check_interval = 60  # seconds

        # Register message handlers
        self.message_bus.add_handler(
            MessageType.ESCALATION, self._handle_escalation
        )
        self.message_bus.add_handler(
            MessageType.ALERT, self._handle_alert
        )

    async def start(self) -> None:
        """Start the orchestrator."""
        self._running = True
        await self.message_bus.start()
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._suggestion_loop())

    async def stop(self) -> None:
        """Stop the orchestrator."""
        self._running = False
        await self.message_bus.stop()

    def register_team(self, team: BaseTeam) -> None:
        """Register a team with the orchestrator."""
        self.state.teams[team.team_id] = team
        self.message_bus.register_team(team)

    def unregister_team(self, team_id: str) -> None:
        """Unregister a team."""
        if team_id in self.state.teams:
            self.message_bus.unregister_team(team_id)
            del self.state.teams[team_id]

    async def assign_task(
        self,
        task: Dict[str, Any],
        target_team: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Assign a task to appropriate team and agent."""
        if target_team and target_team in self.state.teams:
            team = self.state.teams[target_team]
        else:
            team = await self._select_best_team(task)

        if team is None:
            raise ValueError("No available team for task")

        agent_id = await team.assign_task(task)
        return team.team_id, agent_id or "queued"

    async def _select_best_team(self, task: Dict[str, Any]) -> Optional[BaseTeam]:
        """Select the best team for a task based on type and availability."""
        task_type = task.get("type", "general")

        # Team specialization mapping
        specializations = {
            "research": "T01",
            "marketing": "T02",
            "security": "T03",
            "analytics": "T04",
            "video": "T05",
            "compliance": "T06",
            "content": "T07",
            "integration": "T08",
            "orchestration": "T09",
            "quality": "T10",
        }

        target_id = specializations.get(task_type)
        if target_id and target_id in self.state.teams:
            team = self.state.teams[target_id]
            if team.status in [TeamStatus.HEALTHY, TeamStatus.DEGRADED]:
                return team

        # Fall back to any healthy team
        for team in self.state.teams.values():
            if team.status == TeamStatus.HEALTHY:
                return team

        # Accept degraded if no healthy
        for team in self.state.teams.values():
            if team.status == TeamStatus.DEGRADED:
                return team

        return None

    async def conduct_cross_team_vote(
        self,
        topic: str,
        options: List[str],
        participating_teams: Optional[List[str]] = None,
        strategy: VotingStrategy = VotingStrategy.WEIGHTED,
    ) -> VoteResult:
        """Conduct a vote across multiple teams."""
        teams = (
            [self.state.teams[t] for t in participating_teams if t in self.state.teams]
            if participating_teams
            else list(self.state.teams.values())
        )

        # Collect all team votes
        team_votes = []
        for team in teams:
            result = await team.vote(topic, options, strategy=strategy)
            if result.winner:
                team_votes.append(result)

        # Aggregate team decisions
        if not team_votes:
            return VoteResult(
                topic=topic,
                winner=None,
                votes=[],
                strategy=strategy,
                consensus_reached=False,
                confidence=0.0,
                vote_counts={opt: 0 for opt in options},
                participation_rate=0.0,
                duration_ms=0,
            )

        # Count team-level votes
        vote_counts: Dict[str, int] = {opt: 0 for opt in options}
        for result in team_votes:
            if result.winner:
                vote_counts[result.winner] += 1

        winner = max(vote_counts, key=lambda k: vote_counts[k])
        total = len(team_votes)
        consensus = vote_counts[winner] > total / 2

        return VoteResult(
            topic=topic,
            winner=winner if consensus else None,
            votes=[],
            strategy=strategy,
            consensus_reached=consensus,
            confidence=vote_counts[winner] / total if total else 0,
            vote_counts=vote_counts,
            participation_rate=len(team_votes) / len(teams) if teams else 0,
            duration_ms=0,
        )

    async def _handle_escalation(self, message: Any) -> None:
        """Handle escalation from teams."""
        payload = message.payload
        self.state.pending_escalations.append({
            "from": message.source_id,
            "issue": payload.get("issue"),
            "severity": payload.get("severity"),
            "context": payload.get("context"),
            "timestamp": datetime.utcnow(),
        })

        # Auto-handle critical escalations
        if payload.get("severity") == "critical":
            await self._handle_critical_escalation(payload)

    async def _handle_critical_escalation(self, payload: Dict[str, Any]) -> None:
        """Handle critical escalations requiring immediate action."""
        issue = payload.get("issue", "")

        if "security" in issue.lower():
            # Notify security team
            await self.message_bus.send_direct(
                source_id="orchestrator",
                target_id="T03",
                payload={"type": "critical_alert", "issue": issue},
                priority=MessagePriority.CRITICAL,
            )

    async def _handle_alert(self, message: Any) -> None:
        """Handle alerts from teams."""
        # Log and potentially broadcast
        pass

    async def _health_check_loop(self) -> None:
        """Periodic health check of all teams."""
        while self._running:
            await asyncio.sleep(self._health_check_interval)
            await self._check_all_teams_health()

    async def _check_all_teams_health(self) -> Dict[str, TeamStatus]:
        """Check health of all registered teams."""
        health = {}
        critical_teams = []

        for team_id, team in self.state.teams.items():
            status = team.status
            health[team_id] = status

            if status == TeamStatus.CRITICAL:
                critical_teams.append(team_id)
            elif status == TeamStatus.OFFLINE:
                critical_teams.append(team_id)

        self.state.last_health_check = datetime.utcnow()

        # Generate alerts for critical teams
        for team_id in critical_teams:
            await self._generate_team_alert(team_id)

        return health

    async def _generate_team_alert(self, team_id: str) -> None:
        """Generate alert for unhealthy team."""
        team = self.state.teams.get(team_id)
        if not team:
            return

        await self.message_bus.broadcast(
            source_id="orchestrator",
            payload={
                "alert_type": "team_health",
                "team_id": team_id,
                "status": team.status.value,
                "timestamp": datetime.utcnow().isoformat(),
            },
            topic="system_alerts",
            priority=MessagePriority.HIGH,
        )

    async def _suggestion_loop(self) -> None:
        """Generate workflow improvement suggestions."""
        while self._running:
            await asyncio.sleep(3600)  # Every hour
            await self._generate_suggestions()

    async def _generate_suggestions(self) -> None:
        """Analyze system and generate improvement suggestions."""
        suggestions = []

        # Check for bottlenecks
        for team_id, team in self.state.teams.items():
            metrics = team.metrics

            # Slow task completion
            if metrics.avg_task_duration_ms > 10000:  # > 10 seconds
                suggestions.append(WorkflowSuggestion(
                    suggestion_id=f"perf_{team_id}_{datetime.utcnow().timestamp()}",
                    category="bottleneck_detection",
                    description=f"Team {team.name} has slow average task time ({metrics.avg_task_duration_ms}ms)",
                    impact="high",
                    effort="medium",
                    affected_teams=[team_id],
                    priority=7,
                ))

            # Low consensus rate
            if metrics.consensus_rate < 0.7 and metrics.votes_conducted > 5:
                suggestions.append(WorkflowSuggestion(
                    suggestion_id=f"vote_{team_id}_{datetime.utcnow().timestamp()}",
                    category="voting_optimization",
                    description=f"Team {team.name} has low consensus rate ({metrics.consensus_rate:.1%})",
                    impact="medium",
                    effort="low",
                    affected_teams=[team_id],
                    priority=5,
                ))

            # High failure rate
            total_tasks = metrics.tasks_completed + metrics.tasks_failed
            if total_tasks > 10:
                failure_rate = metrics.tasks_failed / total_tasks
                if failure_rate > 0.2:
                    suggestions.append(WorkflowSuggestion(
                        suggestion_id=f"fail_{team_id}_{datetime.utcnow().timestamp()}",
                        category="reliability",
                        description=f"Team {team.name} has high failure rate ({failure_rate:.1%})",
                        impact="high",
                        effort="high",
                        affected_teams=[team_id],
                        priority=8,
                    ))

        self.state.workflow_suggestions.extend(suggestions)
        # Keep only recent suggestions
        self.state.workflow_suggestions = self.state.workflow_suggestions[-100:]

    def get_dashboard_status(self) -> Dict[str, Any]:
        """Get full dashboard status."""
        return {
            "teams": {
                team_id: team.get_status()
                for team_id, team in self.state.teams.items()
            },
            "pending_escalations": len(self.state.pending_escalations),
            "workflow_suggestions": [
                {
                    "id": s.suggestion_id,
                    "category": s.category,
                    "description": s.description,
                    "priority": s.priority,
                }
                for s in self.state.workflow_suggestions[-10:]
            ],
            "improvement_phase": self.state.improvement_cycle_phase,
            "last_health_check": (
                self.state.last_health_check.isoformat()
                if self.state.last_health_check
                else None
            ),
            "message_bus_stats": self.message_bus.get_stats(),
        }

    async def reassign_agent(
        self,
        agent_id: str,
        from_team: str,
        to_team: str,
    ) -> bool:
        """Reassign an agent between teams."""
        if from_team not in self.state.teams or to_team not in self.state.teams:
            return False

        source = self.state.teams[from_team]
        target = self.state.teams[to_team]

        if agent_id not in source.agents:
            return False

        agent = source.agents[agent_id]
        if source.remove_agent(agent_id):
            agent.team_id = to_team
            return target.add_agent(agent)

        return False
