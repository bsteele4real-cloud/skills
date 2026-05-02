"""Inter-agent and inter-team message bus for communication."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING
from datetime import datetime
import asyncio
import uuid
from collections import defaultdict

if TYPE_CHECKING:
    from .agent_base import BaseAgent
    from .team_base import BaseTeam


class MessageType(Enum):
    TASK = "task"
    TASK_RESULT = "task_result"
    VOTE_REQUEST = "vote_request"
    VOTE_RESPONSE = "vote_response"
    BROADCAST = "broadcast"
    DIRECT = "direct"
    STATUS_CHECK = "status_check"
    STATUS_RESPONSE = "status_response"
    ALERT = "alert"
    ESCALATION = "escalation"


class MessagePriority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class Message:
    message_id: str
    message_type: MessageType
    source_id: str  # Agent or Team ID
    target_id: Optional[str]  # None for broadcast
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    requires_ack: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 300  # Time to live
    correlation_id: Optional[str] = None  # For request-response tracking
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        msg_type: MessageType,
        source: str,
        target: Optional[str],
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        requires_ack: bool = False,
        correlation_id: Optional[str] = None,
    ) -> "Message":
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=msg_type,
            source_id=source,
            target_id=target,
            payload=payload,
            priority=priority,
            requires_ack=requires_ack,
            correlation_id=correlation_id,
        )


@dataclass
class MessageAck:
    message_id: str
    receiver_id: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class MessageBus:
    """Central message bus for inter-agent communication."""

    def __init__(self):
        self._agents: Dict[str, "BaseAgent"] = {}
        self._teams: Dict[str, "BaseTeam"] = {}
        self._subscriptions: Dict[str, Set[str]] = defaultdict(set)  # topic -> agent_ids
        self._message_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self._pending_acks: Dict[str, asyncio.Future] = {}
        self._message_log: List[Message] = []
        self._running = False
        self._max_log_size = 10000

    def register_agent(self, agent: "BaseAgent") -> None:
        """Register an agent with the message bus."""
        self._agents[agent.agent_id] = agent

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the message bus."""
        if agent_id in self._agents:
            del self._agents[agent_id]
        # Clean up subscriptions
        for topic in self._subscriptions:
            self._subscriptions[topic].discard(agent_id)

    def register_team(self, team: "BaseTeam") -> None:
        """Register a team with the message bus."""
        self._teams[team.team_id] = team
        for agent in team.agents.values():
            self.register_agent(agent)

    def unregister_team(self, team_id: str) -> None:
        """Unregister a team and its agents."""
        if team_id in self._teams:
            team = self._teams[team_id]
            for agent_id in team.agents:
                self.unregister_agent(agent_id)
            del self._teams[team_id]

    def subscribe(self, agent_id: str, topic: str) -> None:
        """Subscribe an agent to a topic."""
        self._subscriptions[topic].add(agent_id)

    def unsubscribe(self, agent_id: str, topic: str) -> None:
        """Unsubscribe an agent from a topic."""
        self._subscriptions[topic].discard(agent_id)

    def add_handler(
        self, msg_type: MessageType, handler: Callable[[Message], Any]
    ) -> None:
        """Add a message handler for a message type."""
        self._handlers[msg_type].append(handler)

    async def send(self, message: Message) -> Optional[MessageAck]:
        """Send a message to target(s)."""
        self._log_message(message)

        # Priority queue uses (priority, timestamp, message) for ordering
        priority_value = -message.priority.value  # Negative for max-heap behavior
        await self._message_queue.put(
            (priority_value, message.timestamp.timestamp(), message)
        )

        if message.requires_ack:
            future: asyncio.Future = asyncio.Future()
            self._pending_acks[message.message_id] = future
            try:
                ack = await asyncio.wait_for(future, timeout=30)
                return ack
            except asyncio.TimeoutError:
                del self._pending_acks[message.message_id]
                return MessageAck(
                    message_id=message.message_id,
                    receiver_id="",
                    success=False,
                    error="timeout",
                )

        return None

    async def send_direct(
        self,
        source_id: str,
        target_id: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> None:
        """Send a direct message to a specific agent."""
        message = Message.create(
            msg_type=MessageType.DIRECT,
            source=source_id,
            target=target_id,
            payload=payload,
            priority=priority,
        )
        await self.send(message)

    async def broadcast(
        self,
        source_id: str,
        payload: Dict[str, Any],
        topic: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> None:
        """Broadcast a message to all agents or topic subscribers."""
        message = Message.create(
            msg_type=MessageType.BROADCAST,
            source=source_id,
            target=None,
            payload=payload,
            priority=priority,
        )
        message.metadata["topic"] = topic
        await self.send(message)

    async def request_vote(
        self,
        source_id: str,
        team_id: str,
        topic: str,
        options: List[str],
        context: Dict[str, Any],
    ) -> str:
        """Send a vote request to a team. Returns correlation ID."""
        correlation_id = str(uuid.uuid4())
        message = Message.create(
            msg_type=MessageType.VOTE_REQUEST,
            source=source_id,
            target=team_id,
            payload={"topic": topic, "options": options, "context": context},
            priority=MessagePriority.HIGH,
            correlation_id=correlation_id,
        )
        await self.send(message)
        return correlation_id

    async def escalate(
        self,
        source_id: str,
        issue: str,
        severity: str,
        context: Dict[str, Any],
    ) -> None:
        """Escalate an issue to the orchestration team."""
        message = Message.create(
            msg_type=MessageType.ESCALATION,
            source=source_id,
            target="T09",  # Orchestration team
            payload={"issue": issue, "severity": severity, "context": context},
            priority=MessagePriority.CRITICAL,
        )
        await self.send(message)

    async def start(self) -> None:
        """Start the message bus processing loop."""
        self._running = True
        asyncio.create_task(self._process_loop())

    async def stop(self) -> None:
        """Stop the message bus."""
        self._running = False

    async def _process_loop(self) -> None:
        """Main message processing loop."""
        while self._running:
            try:
                # Wait for message with timeout
                try:
                    _, _, message = await asyncio.wait_for(
                        self._message_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Check TTL
                age = (datetime.utcnow() - message.timestamp).total_seconds()
                if age > message.ttl_seconds:
                    continue

                # Route message
                await self._route_message(message)

            except Exception as e:
                # Log error but keep running
                print(f"Message bus error: {e}")

    async def _route_message(self, message: Message) -> None:
        """Route message to appropriate recipient(s)."""
        # Call registered handlers
        for handler in self._handlers.get(message.message_type, []):
            try:
                await handler(message)
            except Exception:
                pass

        if message.message_type == MessageType.BROADCAST:
            await self._handle_broadcast(message)
        elif message.target_id:
            await self._deliver_to_target(message)

    async def _handle_broadcast(self, message: Message) -> None:
        """Handle broadcast message."""
        topic = message.metadata.get("topic")

        if topic and topic in self._subscriptions:
            # Send to topic subscribers
            targets = self._subscriptions[topic]
        else:
            # Send to all agents
            targets = set(self._agents.keys())

        targets.discard(message.source_id)  # Don't send to source

        for agent_id in targets:
            if agent_id in self._agents:
                await self._agents[agent_id].receive_message(
                    {"type": message.message_type.value, "payload": message.payload}
                )

    async def _deliver_to_target(self, message: Message) -> None:
        """Deliver message to specific target."""
        target_id = message.target_id

        # Try agent first
        if target_id in self._agents:
            agent = self._agents[target_id]
            await agent.receive_message(
                {
                    "type": message.message_type.value,
                    "payload": message.payload,
                    "request_id": message.message_id,
                    "correlation_id": message.correlation_id,
                }
            )
            if message.requires_ack:
                self._send_ack(message.message_id, target_id, True)

        # Try team
        elif target_id in self._teams:
            team = self._teams[target_id]
            await team.broadcast(
                {
                    "type": message.message_type.value,
                    "payload": message.payload,
                    "request_id": message.message_id,
                }
            )
            if message.requires_ack:
                self._send_ack(message.message_id, target_id, True)

    def _send_ack(self, message_id: str, receiver_id: str, success: bool) -> None:
        """Send acknowledgment for a message."""
        if message_id in self._pending_acks:
            ack = MessageAck(
                message_id=message_id, receiver_id=receiver_id, success=success
            )
            self._pending_acks[message_id].set_result(ack)
            del self._pending_acks[message_id]

    def _log_message(self, message: Message) -> None:
        """Log message for audit trail."""
        self._message_log.append(message)
        # Trim log if too large
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size // 2 :]

    def get_message_log(
        self,
        limit: int = 100,
        msg_type: Optional[MessageType] = None
    ) -> List[Message]:
        """Get recent messages from log."""
        if msg_type:
            filtered = [m for m in self._message_log if m.message_type == msg_type]
            return filtered[-limit:]
        return self._message_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics."""
        return {
            "registered_agents": len(self._agents),
            "registered_teams": len(self._teams),
            "subscriptions": {
                topic: len(subs) for topic, subs in self._subscriptions.items()
            },
            "pending_acks": len(self._pending_acks),
            "message_log_size": len(self._message_log),
            "running": self._running,
        }


# Global message bus instance
_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Get or create the global message bus."""
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
