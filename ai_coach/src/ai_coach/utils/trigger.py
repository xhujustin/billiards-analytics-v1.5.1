"""Simple event trigger helpers used by higher-level AI Coach workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class EventTrigger:
    """Track repeated events and fire only after a threshold is reached."""

    threshold: int = 1
    counters: Dict[str, int] = field(default_factory=dict)

    def hit(self, event_name: str) -> bool:
        """Record an event and return True when it should trigger."""

        current = self.counters.get(event_name, 0) + 1
        self.counters[event_name] = current
        return current >= self.threshold

    def reset(self, event_name: str | None = None) -> None:
        """Reset one event counter or all tracked counters."""

        if event_name is None:
            self.counters.clear()
            return

        self.counters.pop(event_name, None)

    def snapshot(self) -> Dict[str, int]:
        """Expose a copy of the current counter state."""

        return dict(self.counters)


def should_trigger(payload: Dict[str, Any], key: str, expected: Any = True) -> bool:
    """Convenience helper for predicate-style event checks."""

    return payload.get(key) == expected
