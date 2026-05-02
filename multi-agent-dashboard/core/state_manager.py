"""Shared state management for multi-agent system."""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import asyncio
import json
from pathlib import Path
from enum import Enum


class StateScope(Enum):
    GLOBAL = "global"
    TEAM = "team"
    AGENT = "agent"
    SESSION = "session"


@dataclass
class StateEntry:
    key: str
    value: Any
    scope: StateScope
    owner_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class StateManager:
    """Centralized state management with persistence."""

    def __init__(self, persistence_path: Optional[Path] = None):
        self._state: Dict[str, StateEntry] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._watchers: Dict[str, List[asyncio.Queue]] = {}
        self._persistence_path = persistence_path
        self._dirty = False

    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create lock for a key."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def get(
        self,
        key: str,
        scope: StateScope = StateScope.GLOBAL,
        owner_id: str = "",
    ) -> Optional[Any]:
        """Get a value from state."""
        full_key = self._make_key(key, scope, owner_id)

        entry = self._state.get(full_key)
        if entry is None:
            return None

        # Check TTL
        if entry.ttl_seconds:
            age = (datetime.utcnow() - entry.updated_at).total_seconds()
            if age > entry.ttl_seconds:
                await self.delete(key, scope, owner_id)
                return None

        return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        scope: StateScope = StateScope.GLOBAL,
        owner_id: str = "",
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Set a value in state."""
        full_key = self._make_key(key, scope, owner_id)

        async with self._get_lock(full_key):
            existing = self._state.get(full_key)
            version = (existing.version + 1) if existing else 1

            entry = StateEntry(
                key=key,
                value=value,
                scope=scope,
                owner_id=owner_id,
                version=version,
                ttl_seconds=ttl_seconds,
                metadata=metadata or {},
            )
            if existing:
                entry.created_at = existing.created_at

            self._state[full_key] = entry
            self._dirty = True

            # Notify watchers
            await self._notify_watchers(full_key, entry)

    async def delete(
        self,
        key: str,
        scope: StateScope = StateScope.GLOBAL,
        owner_id: str = "",
    ) -> bool:
        """Delete a value from state."""
        full_key = self._make_key(key, scope, owner_id)

        async with self._get_lock(full_key):
            if full_key in self._state:
                del self._state[full_key]
                self._dirty = True
                return True
            return False

    async def update(
        self,
        key: str,
        updates: Dict[str, Any],
        scope: StateScope = StateScope.GLOBAL,
        owner_id: str = "",
    ) -> bool:
        """Update a dict value in state."""
        full_key = self._make_key(key, scope, owner_id)

        async with self._get_lock(full_key):
            entry = self._state.get(full_key)
            if entry is None:
                return False

            if not isinstance(entry.value, dict):
                return False

            entry.value.update(updates)
            entry.updated_at = datetime.utcnow()
            entry.version += 1
            self._dirty = True

            await self._notify_watchers(full_key, entry)
            return True

    async def increment(
        self,
        key: str,
        amount: int = 1,
        scope: StateScope = StateScope.GLOBAL,
        owner_id: str = "",
    ) -> int:
        """Atomically increment a numeric value."""
        full_key = self._make_key(key, scope, owner_id)

        async with self._get_lock(full_key):
            entry = self._state.get(full_key)
            if entry is None:
                await self.set(key, amount, scope, owner_id)
                return amount

            if not isinstance(entry.value, (int, float)):
                raise ValueError(f"Cannot increment non-numeric value: {type(entry.value)}")

            entry.value += amount
            entry.updated_at = datetime.utcnow()
            entry.version += 1
            self._dirty = True

            return entry.value

    def _make_key(self, key: str, scope: StateScope, owner_id: str) -> str:
        """Create full key from components."""
        return f"{scope.value}:{owner_id}:{key}"

    async def watch(
        self,
        key: str,
        scope: StateScope = StateScope.GLOBAL,
        owner_id: str = "",
    ) -> asyncio.Queue:
        """Watch for changes to a key."""
        full_key = self._make_key(key, scope, owner_id)

        if full_key not in self._watchers:
            self._watchers[full_key] = []

        queue: asyncio.Queue = asyncio.Queue()
        self._watchers[full_key].append(queue)
        return queue

    async def unwatch(
        self,
        key: str,
        queue: asyncio.Queue,
        scope: StateScope = StateScope.GLOBAL,
        owner_id: str = "",
    ) -> None:
        """Stop watching a key."""
        full_key = self._make_key(key, scope, owner_id)

        if full_key in self._watchers:
            if queue in self._watchers[full_key]:
                self._watchers[full_key].remove(queue)

    async def _notify_watchers(self, full_key: str, entry: StateEntry) -> None:
        """Notify all watchers of a key change."""
        if full_key not in self._watchers:
            return

        for queue in self._watchers[full_key]:
            try:
                await queue.put({
                    "key": entry.key,
                    "value": entry.value,
                    "version": entry.version,
                    "updated_at": entry.updated_at.isoformat(),
                })
            except Exception:
                pass

    async def list_keys(
        self,
        scope: Optional[StateScope] = None,
        owner_id: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> List[str]:
        """List keys matching criteria."""
        keys = []
        for full_key, entry in self._state.items():
            if scope and entry.scope != scope:
                continue
            if owner_id and entry.owner_id != owner_id:
                continue
            if prefix and not entry.key.startswith(prefix):
                continue
            keys.append(entry.key)
        return keys

    async def get_all(
        self,
        scope: Optional[StateScope] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all state entries matching criteria."""
        result = {}
        for full_key, entry in self._state.items():
            if scope and entry.scope != scope:
                continue
            if owner_id and entry.owner_id != owner_id:
                continue

            # Check TTL
            if entry.ttl_seconds:
                age = (datetime.utcnow() - entry.updated_at).total_seconds()
                if age > entry.ttl_seconds:
                    continue

            result[entry.key] = entry.value
        return result

    async def save(self) -> None:
        """Persist state to disk."""
        if not self._persistence_path or not self._dirty:
            return

        data = {}
        for full_key, entry in self._state.items():
            data[full_key] = {
                "key": entry.key,
                "value": entry.value,
                "scope": entry.scope.value,
                "owner_id": entry.owner_id,
                "created_at": entry.created_at.isoformat(),
                "updated_at": entry.updated_at.isoformat(),
                "version": entry.version,
                "ttl_seconds": entry.ttl_seconds,
                "metadata": entry.metadata,
            }

        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._persistence_path, "w") as f:
            json.dump(data, f, indent=2)

        self._dirty = False

    async def load(self) -> None:
        """Load state from disk."""
        if not self._persistence_path or not self._persistence_path.exists():
            return

        with open(self._persistence_path, "r") as f:
            data = json.load(f)

        for full_key, entry_data in data.items():
            self._state[full_key] = StateEntry(
                key=entry_data["key"],
                value=entry_data["value"],
                scope=StateScope(entry_data["scope"]),
                owner_id=entry_data["owner_id"],
                created_at=datetime.fromisoformat(entry_data["created_at"]),
                updated_at=datetime.fromisoformat(entry_data["updated_at"]),
                version=entry_data["version"],
                ttl_seconds=entry_data.get("ttl_seconds"),
                metadata=entry_data.get("metadata", {}),
            )

        self._dirty = False

    def get_stats(self) -> Dict[str, Any]:
        """Get state manager statistics."""
        scope_counts = {}
        for entry in self._state.values():
            scope = entry.scope.value
            scope_counts[scope] = scope_counts.get(scope, 0) + 1

        return {
            "total_entries": len(self._state),
            "by_scope": scope_counts,
            "watchers": sum(len(w) for w in self._watchers.values()),
            "dirty": self._dirty,
        }


# Global state manager instance
_state_manager: Optional[StateManager] = None


def get_state_manager(persistence_path: Optional[Path] = None) -> StateManager:
    """Get or create the global state manager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(persistence_path)
    return _state_manager
