"""短期记忆：保存行动与反思轨迹，供后续轮次构建提示词。

项目来源：https://hello-agents.datawhale.cc/
记录仅保存在内存中，不会写入磁盘。
"""

from typing import Dict, List, Optional


class Memory:
    """按时间顺序存储执行结果和反思反馈。"""

    def __init__(self) -> None:
        self.records: List[Dict[str, str]] = []

    def add_record(self, record_type: str, content: str) -> None:
        """添加 execution（执行结果）或 reflection（反思反馈）记录。"""
        if record_type not in ("execution", "reflection"):
            raise ValueError("record_type 必须是 'execution' 或 'reflection'")
        self.records.append({"type": record_type, "content": content})
        print(f"📝 记忆已更新，新增一条 '{record_type}' 记录。")

    def get_trajectory(self) -> str:
        """将全部记录按添加顺序拼接成可用于提示词的文本。"""
        trajectory_parts = []
        for record in self.records:
            if record["type"] == "execution":
                trajectory_parts.append(f"--- 上一轮尝试 (代码) ---\n{record['content']}")
            elif record["type"] == "reflection":
                trajectory_parts.append(f"--- 评审员反馈 ---\n{record['content']}")
        return "\n\n".join(trajectory_parts)

    def get_last_execution(self) -> Optional[str]:
        """返回最近一次执行结果；没有执行记录时返回 None。"""
        for record in reversed(self.records):
            if record["type"] == "execution":
                return record["content"]
        return None
