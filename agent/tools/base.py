from abc import ABC, abstractmethod
from typing import Any, ClassVar


class Tool(ABC):
    """Abstract base for all agent tools.

    Subclasses define class attributes:
      - name: function-call identifier (snake_case, must match LLM schema)
      - description: 1-line natural language description for the LLM
      - parameters: JSON Schema (object) describing run() kwargs

    And implement run() with the actual side effect / computation.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict]

    @abstractmethod
    def run(self, **kwargs: Any) -> Any: ...

    def schema(self) -> dict:
        """Return OpenAI function-calling tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
