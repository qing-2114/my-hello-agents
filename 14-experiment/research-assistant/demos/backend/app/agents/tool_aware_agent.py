"""项目自己的工具调用监听扩展。"""
import logging
from copy import deepcopy
from typing import Any, Callable

from hello_agents import HelloAgentsLLM, SimpleAgent
from hello_agents.tools import ToolRegistry

ToolCallListener = Callable[[dict[str, Any]], None]
logger = logging.getLogger(__name__)


class ToolAwareSimpleAgent(SimpleAgent):
    """保留 SimpleAgent 的执行语义，每次工具执行后通知监听器。"""

    def __init__(
        self, name: str, system_prompt: str, llm: HelloAgentsLLM,
        tool_registry: ToolRegistry | None = None,
        tool_call_listener: ToolCallListener | None = None,
    ):
        super().__init__(name=name, system_prompt=system_prompt, llm=llm,
                         tool_registry=tool_registry)
        self._tool_call_listener = tool_call_listener

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        parsed_parameters = {}
        try:
            # 当前 hello-agents 使用此接口；示例中的 _parse_parameters 不存在。
            # 拷贝执行前参数，避免工具或监听器修改参数影响事件含义。
            parsed_parameters = deepcopy(self._parse_tool_parameters(tool_name, parameters))
        except Exception:
            # 仍交给父类返回它约定的错误结果。
            pass
        result = super()._execute_tool_call(tool_name, parameters)
        if self._tool_call_listener is not None:
            try:
                self._tool_call_listener({
                    'agent_name': self.name,
                    'tool_name': tool_name,
                    'parsed_parameters': parsed_parameters,
                    'result': result,
                })
            except Exception:
                # 不记录参数、结果或异常内容，防止日志泄漏敏感资料。
                logger.warning('工具调用监听器失败，工具结果仍正常返回')
        return result
