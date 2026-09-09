"""基于 HelloAgents 框架扩展的简单对话 Agent。"""

import re
from typing import Iterator, Optional

from hello_agents import Config, HelloAgentsLLM, Message, SimpleAgent, ToolRegistry


class MySimpleAgent(SimpleAgent):
    """支持文本工具调用和流式响应的简单对话 Agent。"""

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_registry: Optional[ToolRegistry] = None,
        enable_tool_calling: bool = True,
    ) -> None:
        super().__init__(name, llm, system_prompt, config)
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling and tool_registry is not None
        status = "启用" if self.enable_tool_calling else "禁用"
        print(f"✅ {name} 初始化完成，工具调用: {status}")

    def run(self, input_text: str, max_tool_iterations: int = 3, **kwargs) -> str:
        """运行 Agent，支持可选的多轮文本工具调用。"""
        if max_tool_iterations < 1:
            raise ValueError("max_tool_iterations 必须大于或等于 1")

        print(f"🤖 {self.name} 正在处理: {input_text}")
        messages = [
            {"role": "system", "content": self._get_enhanced_system_prompt()},
            *(msg.to_dict() for msg in self._history),
            {"role": "user", "content": input_text},
        ]

        if not self.enable_tool_calling:
            response = self.llm.invoke(messages, **kwargs)
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(response, "assistant"))
            print(f"✅ {self.name} 响应完成")
            return response

        return self._run_with_tools(messages, input_text, max_tool_iterations, **kwargs)

    def _get_enhanced_system_prompt(self) -> str:
        """构建包含工具信息和调用格式的系统提示词。"""
        base_prompt = self.system_prompt or "你是一个有用的AI助手。"
        if not self.enable_tool_calling or not self.tool_registry:
            return base_prompt

        tools_description = self.tool_registry.get_tools_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt

        return base_prompt + (
            "\n\n## 可用工具\n"
            "你可以使用以下工具来帮助回答问题:\n"
            f"{tools_description}\n"
            "\n## 工具调用格式\n"
            "当需要使用工具时，请使用以下格式:\n"
            "`[TOOL_CALL:{tool_name}:{parameters}]`\n"
            "例如: `[TOOL_CALL:search:Python编程]` 或 "
            "`[TOOL_CALL:memory:recall=用户信息]`\n\n"
            "工具调用结果会自动插入到对话中，然后你可以基于结果继续回答。\n"
        )

    def _run_with_tools(
        self,
        messages: list[dict[str, str]],
        input_text: str,
        max_tool_iterations: int,
        **kwargs,
    ) -> str:
        """执行支持多轮工具调用的对话循环。"""
        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            response = self.llm.invoke(messages, **kwargs)
            tool_calls = self._parse_tool_calls(response)
            if not tool_calls:
                final_response = response
                break

            print(f"🔧 检测到 {len(tool_calls)} 个工具调用")
            tool_results = []
            clean_response = response
            for call in tool_calls:
                result = self._execute_tool_call(
                    call["tool_name"], call["parameters"]
                )
                tool_results.append(result)
                clean_response = clean_response.replace(call["original"], "")

            messages.append(
                {"role": "assistant", "content": clean_response.strip()}
            )
            tool_results_text = "\n\n".join(tool_results)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"工具执行结果:\n{tool_results_text}\n\n"
                        "请基于这些结果给出完整的回答。"
                    ),
                }
            )
            current_iteration += 1

        if not final_response:
            final_response = self.llm.invoke(messages, **kwargs)

        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_response, "assistant"))
        print(f"✅ {self.name} 响应完成")
        return final_response

    def _parse_tool_calls(self, text: str) -> list[dict[str, str]]:
        """解析 ``[TOOL_CALL:工具名:参数]`` 格式的工具调用。"""
        pattern = r"\[TOOL_CALL:([^:\]]+):([^\]]+)\]"
        return [
            {
                "tool_name": match.group(1).strip(),
                "parameters": match.group(2).strip(),
                "original": match.group(0),
            }
            for match in re.finditer(pattern, text)
        ]

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """执行一次工具调用，并把结果转换成供 LLM 阅读的文本。"""
        if not self.tool_registry:
            return "❌ 错误: 未配置工具注册表"

        try:
            actual_tool_name = tool_name
            if (
                tool_name == "calculator"
                and not self.tool_registry.get_tool(tool_name)
                and self.tool_registry.get_tool("python_calculator")
            ):
                actual_tool_name = "python_calculator"

            if actual_tool_name in {"calculator", "python_calculator"}:
                result = self.tool_registry.execute_tool(actual_tool_name, parameters)
            else:
                tool = self.tool_registry.get_tool(actual_tool_name)
                if tool:
                    param_dict = self._parse_tool_parameters(
                        actual_tool_name, parameters
                    )
                    result = tool.run(param_dict)
                elif self.tool_registry.get_function(actual_tool_name):
                    result = self.tool_registry.execute_tool(
                        actual_tool_name, parameters
                    )
                else:
                    return f"❌ 错误: 未找到工具 '{tool_name}'"

            return f"🔧 工具 {actual_tool_name} 执行结果:\n{result}"
        except Exception as exc:
            return f"❌ 工具调用失败: {exc}"

    def _parse_tool_parameters(self, tool_name: str, parameters: str) -> dict[str, str]:
        """把简单的文本参数转换成工具需要的字典。"""
        if "=" in parameters:
            param_dict = {}
            for pair in parameters.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    param_dict[key.strip()] = value.strip()
            return param_dict

        if tool_name == "search":
            return {"query": parameters}
        if tool_name == "memory":
            return {"action": "search", "query": parameters}
        return {"input": parameters}

    def stream_run(self, input_text: str, **kwargs) -> Iterator[str]:
        """以流式方式运行 Agent，并在结束后保存完整对话。"""
        print(f"🌊 {self.name} 开始流式处理: {input_text}")
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        messages.extend(msg.to_dict() for msg in self._history)
        messages.append({"role": "user", "content": input_text})

        full_response = ""
        for chunk in self.llm.stream_invoke(messages, **kwargs):
            full_response += chunk
            yield chunk

        self.add_message(Message(input_text, "user"))
        self.add_message(Message(full_response, "assistant"))
        print(f"✅ {self.name} 流式响应完成")

    def add_tool(self, tool) -> None:
        """添加一个工具，并自动启用工具调用。"""
        if not self.tool_registry:
            self.tool_registry = ToolRegistry()

        self.tool_registry.register_tool(tool)
        self.enable_tool_calling = True
        print(f"🔧 工具 '{tool.name}' 已添加")

    def has_tools(self) -> bool:
        """检查当前是否启用了至少一个工具。"""
        return (
            self.enable_tool_calling
            and self.tool_registry is not None
            and bool(self.tool_registry.list_tools())
        )

    def remove_tool(self, tool_name: str) -> bool:
        """移除指定工具；工具存在并被移除时返回 ``True``。"""
        if not self.tool_registry or tool_name not in self.tool_registry.list_tools():
            return False

        self.tool_registry.unregister(tool_name)
        if not self.tool_registry.list_tools():
            self.enable_tool_calling = False
        return True

    def list_tools(self) -> list[str]:
        """列出所有可用工具名称。"""
        if self.tool_registry:
            return self.tool_registry.list_tools()
        return []
