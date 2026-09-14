"""第七章实验：异步并行工具执行器。

项目来源：https://hello-agents.datawhale.cc/

把同步的 ``ToolRegistry.execute_tool`` 放到线程池里，用 ``asyncio.gather``
并行等待多个工具任务。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Optional

from hello_agents import ToolRegistry

try:
    from .tool_chain_manager import create_toolchain_registry
except ImportError:  # 直接运行本文件，或把 tools 目录加入 sys.path 时
    from tool_chain_manager import create_toolchain_registry


class AsyncToolExecutor:
    """异步工具执行器。"""

    def __init__(self, registry: ToolRegistry, max_workers: int = 4) -> None:
        self.registry = registry
        self.executor: Optional[concurrent.futures.ThreadPoolExecutor] = (
            concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        )

    async def execute_tool_async(self, tool_name: str, input_data: str) -> str:
        """异步执行单个工具。"""
        if self.executor is None:
            return f"❌ 工具执行器已关闭，无法执行 '{tool_name}'"

        loop = asyncio.get_running_loop()

        def _execute() -> str:
            return self.registry.execute_tool(tool_name, input_data)

        return await loop.run_in_executor(self.executor, _execute)

    async def execute_tools_parallel(self, tasks: list[dict[str, str]]) -> list[str]:
        """并行执行多个工具。"""
        print(f"开始并行执行 {len(tasks)} 个工具任务")

        async_tasks = [
            self.execute_tool_async(task["tool_name"], task["input_data"])
            for task in tasks
        ]
        results = await asyncio.gather(*async_tasks)

        print("✅ 所有工具任务执行完成")
        return list(results)

    def close(self) -> None:
        """关闭线程池。"""
        if self.executor is not None:
            self.executor.shutdown(wait=True)
            self.executor = None

    def __enter__(self) -> AsyncToolExecutor:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        executor = getattr(self, "executor", None)
        if executor is not None:
            executor.shutdown(wait=False)


async def test_parallel_execution() -> list[str]:
    """测试并行工具执行。"""
    registry = create_toolchain_registry()
    executor = AsyncToolExecutor(registry)

    tasks = [
        {"tool_name": "search", "input_data": "Python编程"},
        {"tool_name": "search", "input_data": "机器学习"},
        {"tool_name": "my_calculator", "input_data": "2 + 2"},
        {"tool_name": "my_calculator", "input_data": "sqrt(16)"},
    ]

    try:
        results = await executor.execute_tools_parallel(tasks)
        for i, result in enumerate(results):
            preview = result if len(result) <= 100 else result[:100] + "..."
            print(f"任务 {i + 1} 结果: {preview}")
        return results
    finally:
        executor.close()


if __name__ == "__main__":
    asyncio.run(test_parallel_execution())
