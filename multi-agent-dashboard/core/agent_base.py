"""Base agent class for multi-agent dashboard system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
import asyncio


class AgentRole(Enum):
    LEAD = "lead"
    SPECIALIST = "specialist"
    WORKER = "worker"
    REVIEWER = "reviewer"


class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    VOTING = "voting"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class AgentConfig:
    agent_id: str
    name: str
    role: AgentRole
    team_id: str
    llm_model: str = "claude-sonnet-4"
    vote_weight: float = 1.0
    capabilities: List[str] = field(default_factory=list)
    system_prompt: str = ""
    max_concurrent_tasks: int = 3


@dataclass
class TaskResult:
    task_id: str
    agent_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent_id = config.agent_id
        self.name = config.name
        self.role = config.role
        self.team_id = config.team_id
        self.status = AgentStatus.IDLE
        self.current_tasks: List[str] = []
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._created_at = datetime.utcnow()

    @property
    def vote_weight(self) -> float:
        weights = {
            AgentRole.LEAD: 2.0,
            AgentRole.SPECIALIST: 1.5,
            AgentRole.REVIEWER: 1.2,
            AgentRole.WORKER: 1.0,
        }
        return self.config.vote_weight or weights.get(self.role, 1.0)

    @abstractmethod
    async def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """Execute a task assigned to this agent."""
        pass

    @abstractmethod
    async def vote(self, topic: str, options: List[str], context: Dict[str, Any]) -> str:
        """Cast a vote on a topic."""
        pass

    async def receive_message(self, message: Dict[str, Any]) -> None:
        """Receive a message from the message bus."""
        await self._message_queue.put(message)

    async def process_messages(self) -> None:
        """Process queued messages."""
        while not self._message_queue.empty():
            message = await self._message_queue.get()
            await self._handle_message(message)

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle a received message."""
        msg_type = message.get("type")
        if msg_type == "task":
            await self.execute_task(message.get("payload", {}))
        elif msg_type == "vote_request":
            await self._handle_vote_request(message)
        elif msg_type == "status_check":
            await self._respond_status(message)

    async def _handle_vote_request(self, message: Dict[str, Any]) -> None:
        """Handle a vote request message."""
        payload = message.get("payload", {})
        vote = await self.vote(
            topic=payload.get("topic", ""),
            options=payload.get("options", []),
            context=payload.get("context", {}),
        )
        # Vote result sent back via message bus
        await self._send_vote_response(message.get("request_id"), vote)

    async def _respond_status(self, message: Dict[str, Any]) -> None:
        """Respond to status check."""
        pass

    async def _send_vote_response(self, request_id: str, vote: str) -> None:
        """Send vote response back."""
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "team_id": self.team_id,
            "status": self.status.value,
            "current_tasks": len(self.current_tasks),
            "vote_weight": self.vote_weight,
            "uptime_seconds": (datetime.utcnow() - self._created_at).total_seconds(),
        }

    def can_accept_task(self) -> bool:
        """Check if agent can accept more tasks."""
        return (
            self.status != AgentStatus.OFFLINE
            and len(self.current_tasks) < self.config.max_concurrent_tasks
        )

    def __repr__(self) -> str:
        return f"<Agent {self.name} ({self.role.value}) @ {self.team_id}>"


class LLMAgent(BaseAgent):
    """Agent powered by an LLM for task execution and voting."""

    def __init__(self, config: AgentConfig, llm_client: Any = None):
        super().__init__(config)
        self.llm_client = llm_client
        self.system_prompt = config.system_prompt

    async def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """Execute task using LLM."""
        task_id = task.get("task_id", str(uuid.uuid4()))
        self.current_tasks.append(task_id)
        self.status = AgentStatus.BUSY
        start_time = datetime.utcnow()

        try:
            result = await self._call_llm(task)
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                success=True,
                result=result,
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return TaskResult(
                task_id=task_id,
                agent_id=self.agent_id,
                success=False,
                result=None,
                error=str(e),
                duration_ms=duration,
            )
        finally:
            self.current_tasks.remove(task_id)
            if not self.current_tasks:
                self.status = AgentStatus.IDLE

    async def vote(self, topic: str, options: List[str], context: Dict[str, Any]) -> str:
        """Cast vote using LLM reasoning."""
        self.status = AgentStatus.VOTING
        try:
            prompt = self._build_vote_prompt(topic, options, context)
            response = await self._call_llm({"prompt": prompt, "task_type": "vote"})
            selected = self._parse_vote_response(response, options)
            return selected
        finally:
            self.status = AgentStatus.IDLE

    def _build_vote_prompt(
        self, topic: str, options: List[str], context: Dict[str, Any]
    ) -> str:
        """Build prompt for voting decision."""
        options_str = "\n".join(f"- {opt}" for opt in options)
        context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
        return f"""You are {self.name}, a {self.role.value} agent.

Topic: {topic}

Options:
{options_str}

Context:
{context_str}

Select the best option and respond with ONLY the option text."""

    def _parse_vote_response(self, response: str, options: List[str]) -> str:
        """Parse LLM response to extract vote."""
        response_lower = response.lower().strip()
        for opt in options:
            if opt.lower() in response_lower:
                return opt
        return options[0]  # Default to first option

    async def _call_llm(self, task: Dict[str, Any]) -> str:
        """Call the LLM. Override for specific implementations."""
        if self.llm_client is None:
            return f"[Mock response for {task.get('task_type', 'task')}]"
        # Actual LLM call implementation
        return await self.llm_client.complete(
            model=self.config.llm_model,
            system=self.system_prompt,
            prompt=task.get("prompt", str(task)),
        )
