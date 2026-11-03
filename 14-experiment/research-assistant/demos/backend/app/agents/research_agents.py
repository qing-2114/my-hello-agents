"""三个独立角色；当前仅消费调用者提供的搜索资料。"""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from hello_agents import HelloAgentsLLM
from hello_agents.tools import ToolRegistry

from .tool_aware_agent import ToolAwareSimpleAgent, ToolCallListener

from ..models.schemas import SummaryState, TodoItem
from .prompts import (
    todo_planner_instructions, task_summarizer_instructions, report_writer_instructions,
)


class _AgentService:
    def __init__(self, llm: HelloAgentsLLM, name: str, system_prompt: str,
                 tool_call_listener: ToolCallListener | None = None,
                 tool_registry: ToolRegistry | None = None):
        self._agent = ToolAwareSimpleAgent(
            name=name, system_prompt=system_prompt, llm=llm,
            tool_registry=tool_registry, tool_call_listener=tool_call_listener,
        )

    def _run(self, prompt: str) -> str:
        # 同一个角色重复调用时不携带上一次研究的历史；实例不用于并发请求。
        self._agent.clear_history()
        try:
            response = self._agent.run(prompt)
            if not isinstance(response, str) or not response.strip():
                raise ValueError('Agent 返回空内容')
            return response.strip()
        finally:
            self._agent.clear_history()


class PlanningService(_AgentService):
    def __init__(self, llm: HelloAgentsLLM,
                 tool_call_listener: ToolCallListener | None = None,
                 tool_registry: ToolRegistry | None = None):
        self._llm = llm
        self._tool_call_listener = tool_call_listener
        super().__init__(llm, 'TODO Planner', '你是一个研究规划专家，擅长将复杂的研究主题分解为清晰的子任务。',
                         tool_call_listener, tool_registry)

    def plan_todo_list(self, state: SummaryState) -> list[TodoItem]:
        if not isinstance(state.research_topic, str) or not state.research_topic.strip():
            raise ValueError('研究主题不能为空')
        prompt = todo_planner_instructions.format(
            current_date=self._get_current_date(),
            research_topic=state.research_topic.strip(),
        )
        payload = self._extract_tasks(self._run(prompt))
        tasks = [TodoItem(id=i, **item) for i, item in enumerate(payload, 1)]
        state.todo_items = tasks
        return tasks

    @staticmethod
    def _get_current_date() -> str:
        return datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日')

    @staticmethod
    def _extract_tasks(response: str) -> list[dict]:
        """解析纯JSON、代码块或说明文字中的数组；不使用贪婪括号正则。"""
        if not isinstance(response, str) or not response.strip():
            raise ValueError('规划响应不能为空')
        text = response.strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            candidates = []
            pos = 0
            while pos < len(text):
                if text[pos] not in '[{':
                    pos += 1
                    continue
                try:
                    value, end = decoder.raw_decode(text, pos)
                except json.JSONDecodeError:
                    pos += 1
                    continue
                if isinstance(value, list):
                    candidates.append(value)
                # 完整跳过JSON值，避免把字符串中的括号或嵌套数组当成任务列表。
                pos = end
            if len(candidates) != 1:
                raise ValueError('无法确定唯一的任务JSON数组，请返回一份完整规划')
            payload = candidates[0]
        if not isinstance(payload, list) or not 3 <= len(payload) <= 5:
            raise ValueError('规划必须包含3-5个子任务')
        tasks = []
        for idx, item in enumerate(payload, 1):
            if not isinstance(item, dict) or any(
                not isinstance(item.get(key), str) or not item[key].strip()
                for key in ('title', 'intent', 'query')
            ):
                raise ValueError(f'任务{idx}必须包含非空 title、intent、query 字符串')
            tasks.append({key: item[key].strip() for key in ('title', 'intent', 'query')})
        return tasks

    @staticmethod
    def evaluate_plan(todo_items: list[TodoItem]) -> dict:
        """规则式质量提示，不代表模型对覆盖度或逻辑关系的语义评估。"""
        score = 100
        suggestions = []
        if len(todo_items) < 3:
            score -= 20
            suggestions.append('子任务数量过少，可能遗漏重要信息')
        elif len(todo_items) > 5:
            score -= 10
            suggestions.append('子任务数量过多，可能存在冗余')
        titles, queries = set(), set()
        for task in todo_items:
            title = task.title.strip()
            query = task.query.strip()
            if not title or not task.intent.strip() or not query:
                score -= 10
                suggestions.append(f'任务{task.id}存在空白标题、意图或查询')
            else:
                # 中文不依赖空格分词；6个汉字仅是启发式阈值。
                chinese_chars = len(re.findall(r'[\u3400-\u9fff]', query))
                words = re.findall(r'[A-Za-z0-9]+', query)
                if chinese_chars < 6 and len(words) < 2:
                    score -= 10
                    suggestions.append(f'任务「{title}」的查询过于简单，建议补充研究对象和检索角度')
            title_key = re.sub(r'\s+', '', title).casefold()
            query_key = re.sub(r'\s+', ' ', query).casefold()
            if (title_key and title_key in titles) or (query_key and query_key in queries):
                score -= 10
                suggestions.append(f'任务「{title}」的标题或查询重复，建议调整研究角度')
            titles.add(title_key)
            queries.add(query_key)
        return {'score': max(0, score), 'suggestions': suggestions}


class SummarizationService(_AgentService):
    def __init__(self, llm: HelloAgentsLLM,
                 tool_call_listener: ToolCallListener | None = None,
                 tool_registry: ToolRegistry | None = None):
        self._llm = llm
        self._tool_call_listener = tool_call_listener
        super().__init__(llm, 'Task Summarizer', '你是一个任务总结专家，擅长从搜索结果中提取关键信息。',
                         tool_call_listener, tool_registry)

    def summarize_task(self, task: TodoItem, search_results: list[dict]) -> tuple[str, list[str]]:
        if not search_results:
            raise ValueError('没有搜索资料，不能生成研究总结')
        summary = self._run(task_summarizer_instructions.format(
            task_title=task.title, task_intent=task.intent, task_query=task.query,
            search_results=self._format_sources(search_results, task.id),
        ))
        return summary, [result['url'] for result in search_results]

    @staticmethod
    def _format_sources(search_results: list[dict], task_id: int) -> str:
        formatted = []
        for idx, result in enumerate(search_results, 1):
            if any(not isinstance(result.get(k), str) or not result[k].strip()
                   for k in ('title', 'url', 'snippet')):
                raise ValueError('资料必须包含非空 title、url、snippet')
            if not result['url'].startswith(('https://', 'http://')):
                raise ValueError('来源URL必须为HTTP或HTTPS')
            formatted.append(
                f"[T{task_id}-S{idx}] {result['title']}\nURL: {result['url']}\n摘要: {result['snippet']}"
            )
        return '\n\n'.join(formatted)


class ReportingService(_AgentService):
    def __init__(self, llm: HelloAgentsLLM,
                 tool_call_listener: ToolCallListener | None = None,
                 tool_registry: ToolRegistry | None = None):
        self._llm = llm
        self._tool_call_listener = tool_call_listener
        super().__init__(llm, 'Report Writer', '你是一个报告撰写专家，擅长整合信息并生成结构化的报告。',
                         tool_call_listener, tool_registry)

    def generate_report(self, research_topic: str, task_summaries: list[tuple[TodoItem, str, list[str]]]) -> str:
        if not research_topic.strip() or not task_summaries:
            raise ValueError('研究主题和子任务总结不能为空')
        ids = [task.id for task, _, _ in task_summaries]
        if len(set(ids)) != len(ids):
            raise ValueError('任务编号不能重复')
        if any(not summary.strip() for _, summary, _ in task_summaries):
            raise ValueError('子任务总结不能为空')
        if any(not urls or any(not isinstance(url, str) or not url.startswith(('http://', 'https://'))
                               for url in urls) for _, _, urls in task_summaries):
            raise ValueError('每项任务必须提供有效的来源URL列表')
        return self._run(report_writer_instructions.format(
            research_topic=research_topic,
            task_summaries=self._format_summaries(task_summaries),
        ))

    @staticmethod
    def _format_summaries(task_summaries: list[tuple[TodoItem, str, list[str]]]) -> str:
        return '\n\n'.join(
            f'## 任务{task.id}：{task.title}\n\n**意图**：{task.intent}\n\n{summary}\n\n**来源**：\n'
            + '\n'.join(f'- [T{task.id}-S{idx}] {url}' for idx, url in enumerate(urls, 1))
            for task, summary, urls in task_summaries
        )
