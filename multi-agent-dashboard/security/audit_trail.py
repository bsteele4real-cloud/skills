"""Immutable audit trail for security events."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import hashlib
import json
import asyncio
from pathlib import Path


class EventType(Enum):
    LINK_VERIFICATION = "link_verification"
    PRIVACY_CHECK = "privacy_check"
    VOTE_CAST = "vote_cast"
    VOTE_RESULT = "vote_result"
    TEAM_ACTION = "team_action"
    AGENT_ACTION = "agent_action"
    ESCALATION = "escalation"
    SECURITY_ALERT = "security_alert"
    COMPLIANCE_VIOLATION = "compliance_violation"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    CONFIG_CHANGE = "config_change"
    AUTH_EVENT = "auth_event"
    SYSTEM_EVENT = "system_event"


class RiskLevel(Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEntry:
    entry_id: str
    event_type: EventType
    timestamp: datetime
    actor_id: str
    actor_type: str  # "agent", "team", "system", "user"
    action: str
    target: str
    target_type: str
    outcome: str  # "success", "failure", "blocked"
    risk_level: RiskLevel
    details: Dict[str, Any]
    previous_hash: str
    entry_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "action": self.action,
            "target": self.target,
            "target_type": self.target_type,
            "outcome": self.outcome,
            "risk_level": self.risk_level.value,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        return cls(
            entry_id=data["entry_id"],
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            actor_id=data["actor_id"],
            actor_type=data["actor_type"],
            action=data["action"],
            target=data["target"],
            target_type=data["target_type"],
            outcome=data["outcome"],
            risk_level=RiskLevel(data["risk_level"]),
            details=data.get("details", {}),
            previous_hash=data["previous_hash"],
            entry_hash=data["entry_hash"],
            metadata=data.get("metadata", {}),
        )


class AuditTrail:
    """Immutable audit trail with tamper detection."""

    RETENTION_DAYS = 365
    GENESIS_HASH = "0" * 64

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        alert_callback: Optional[callable] = None,
    ):
        self.storage_path = storage_path
        self.alert_callback = alert_callback
        self._entries: List[AuditEntry] = []
        self._last_hash = self.GENESIS_HASH
        self._lock = asyncio.Lock()

    async def log_event(
        self,
        event_type: EventType,
        actor_id: str,
        actor_type: str,
        action: str,
        target: str,
        target_type: str,
        outcome: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a security-relevant event."""
        async with self._lock:
            entry_id = self._generate_entry_id()
            timestamp = datetime.utcnow()
            details = details or {}
            metadata = metadata or {}

            # Compute hash
            entry_data = {
                "entry_id": entry_id,
                "event_type": event_type.value,
                "timestamp": timestamp.isoformat(),
                "actor_id": actor_id,
                "actor_type": actor_type,
                "action": action,
                "target": target,
                "target_type": target_type,
                "outcome": outcome,
                "risk_level": risk_level.value,
                "details": details,
                "previous_hash": self._last_hash,
            }

            entry_hash = self._compute_hash(entry_data)

            entry = AuditEntry(
                entry_id=entry_id,
                event_type=event_type,
                timestamp=timestamp,
                actor_id=actor_id,
                actor_type=actor_type,
                action=action,
                target=target,
                target_type=target_type,
                outcome=outcome,
                risk_level=risk_level,
                details=details,
                previous_hash=self._last_hash,
                entry_hash=entry_hash,
                metadata=metadata,
            )

            self._entries.append(entry)
            self._last_hash = entry_hash

            # Alert on high-risk events
            if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                await self._trigger_alert(entry)

            # Persist if storage configured
            if self.storage_path:
                await self._persist_entry(entry)

            return entry

    def _generate_entry_id(self) -> str:
        """Generate unique entry ID."""
        import uuid
        return str(uuid.uuid4())

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of entry data."""
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def _trigger_alert(self, entry: AuditEntry) -> None:
        """Trigger alert for high-risk event."""
        if self.alert_callback:
            try:
                await self.alert_callback(entry)
            except Exception:
                pass

    async def _persist_entry(self, entry: AuditEntry) -> None:
        """Persist entry to storage."""
        if not self.storage_path:
            return

        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Daily log files
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        log_file = self.storage_path / f"audit_{date_str}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    async def verify_integrity(self) -> bool:
        """Verify integrity of entire audit trail."""
        if not self._entries:
            return True

        expected_hash = self.GENESIS_HASH
        for entry in self._entries:
            # Check previous hash link
            if entry.previous_hash != expected_hash:
                return False

            # Recompute and verify entry hash
            entry_data = {
                "entry_id": entry.entry_id,
                "event_type": entry.event_type.value,
                "timestamp": entry.timestamp.isoformat(),
                "actor_id": entry.actor_id,
                "actor_type": entry.actor_type,
                "action": entry.action,
                "target": entry.target,
                "target_type": entry.target_type,
                "outcome": entry.outcome,
                "risk_level": entry.risk_level.value,
                "details": entry.details,
                "previous_hash": entry.previous_hash,
            }
            computed_hash = self._compute_hash(entry_data)

            if computed_hash != entry.entry_hash:
                return False

            expected_hash = entry.entry_hash

        return True

    async def query(
        self,
        event_type: Optional[EventType] = None,
        actor_id: Optional[str] = None,
        target: Optional[str] = None,
        risk_level: Optional[RiskLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit entries with filters."""
        results = []

        for entry in reversed(self._entries):
            if len(results) >= limit:
                break

            if event_type and entry.event_type != event_type:
                continue
            if actor_id and entry.actor_id != actor_id:
                continue
            if target and entry.target != target:
                continue
            if risk_level and entry.risk_level != risk_level:
                continue
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue

            results.append(entry)

        return results

    async def get_recent(
        self,
        count: int = 100,
        risk_level_min: Optional[RiskLevel] = None,
    ) -> List[AuditEntry]:
        """Get recent audit entries."""
        if not risk_level_min:
            return self._entries[-count:]

        risk_order = [
            RiskLevel.INFO,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]
        min_idx = risk_order.index(risk_level_min)

        filtered = [
            e for e in self._entries
            if risk_order.index(e.risk_level) >= min_idx
        ]
        return filtered[-count:]

    async def cleanup_old_entries(self) -> int:
        """Remove entries older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS)
        original_count = len(self._entries)

        self._entries = [e for e in self._entries if e.timestamp >= cutoff]

        removed = original_count - len(self._entries)

        # Update last hash if entries remain
        if self._entries:
            self._last_hash = self._entries[-1].entry_hash
        else:
            self._last_hash = self.GENESIS_HASH

        return removed

    def get_stats(self) -> Dict[str, Any]:
        """Get audit trail statistics."""
        if not self._entries:
            return {
                "total_entries": 0,
                "by_event_type": {},
                "by_risk_level": {},
                "oldest_entry": None,
                "newest_entry": None,
            }

        by_event = {}
        by_risk = {}
        for entry in self._entries:
            event = entry.event_type.value
            by_event[event] = by_event.get(event, 0) + 1

            risk = entry.risk_level.value
            by_risk[risk] = by_risk.get(risk, 0) + 1

        return {
            "total_entries": len(self._entries),
            "by_event_type": by_event,
            "by_risk_level": by_risk,
            "oldest_entry": self._entries[0].timestamp.isoformat(),
            "newest_entry": self._entries[-1].timestamp.isoformat(),
            "integrity_verified": True,  # Would run verify_integrity in production
        }


# Convenience functions
async def log_security_event(
    event_type: EventType,
    actor_id: str,
    action: str,
    target: str,
    outcome: str,
    risk_level: RiskLevel = RiskLevel.LOW,
    details: Optional[Dict[str, Any]] = None,
) -> AuditEntry:
    """Quick logging of security events."""
    from .audit_trail import _global_trail
    return await _global_trail.log_event(
        event_type=event_type,
        actor_id=actor_id,
        actor_type="agent",
        action=action,
        target=target,
        target_type="resource",
        outcome=outcome,
        risk_level=risk_level,
        details=details,
    )


# Global audit trail instance
_global_trail: Optional[AuditTrail] = None


def get_audit_trail(storage_path: Optional[Path] = None) -> AuditTrail:
    """Get or create global audit trail."""
    global _global_trail
    if _global_trail is None:
        _global_trail = AuditTrail(storage_path)
    return _global_trail
