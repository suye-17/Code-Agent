from abc import ABC, abstractmethod
from typing import Any, ClassVar


class Tool(ABC):
    """所有 Agent 工具的抽象基类。

    子类需要定义三个类属性：
      - name: function-calling 调用名（snake_case，必须与 LLM schema 一致）
      - description: 一行自然语言描述，会传给 LLM 用于决策何时调用
      - parameters: JSON Schema（object），描述 run() 的入参

    并实现 run()：执行真正的副作用 / 计算。
    """

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict]

    @abstractmethod
    def run(self, **kwargs: Any) -> Any: ...

    def schema(self) -> dict:
        """返回 OpenAI function-calling 标准 schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
