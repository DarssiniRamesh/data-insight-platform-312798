from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class MockCollibraAdapter:
    """
    Mock adapter for Collibra integration touchpoints.

    Behavior:
    - Set `should_fail=True` to simulate a validation failure.
    - Calls are recorded in `calls` for assertions.
    """

    should_fail: bool = False
    fail_message: str = "Mock Collibra validation failed."
    calls: List[Dict[str, Any]] = field(default_factory=list)

    def publish_metadata(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Publish metadata to Collibra (mocked)."""
        self.calls.append({"method": "publish_metadata", "payload": payload})
        if self.should_fail:
            return False, {"message": self.fail_message}
        return True, {"message": "ok"}
