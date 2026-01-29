from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class MockImmutaAdapter:
    """
    Mock adapter for Immuta integration touchpoints.

    Behavior:
    - Set `should_deny=True` to simulate a policy denial.
    - Calls are recorded in `calls` for assertions.
    """

    should_deny: bool = False
    deny_message: str = "Denied by Immuta policy."
    calls: List[Dict[str, Any]] = field(default_factory=list)

    def register_dataset(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Register dataset/policy in Immuta (mocked)."""
        self.calls.append({"method": "register_dataset", "payload": payload})
        if self.should_deny:
            return False, {"message": self.deny_message}
        return True, {"message": "ok"}
