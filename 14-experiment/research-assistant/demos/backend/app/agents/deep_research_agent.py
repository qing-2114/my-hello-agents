"""研究角色装配、顺序研究流程与事件转发。"""
from copy import deepcopy
from dataclasses import asdict
import logging
from pathlib import Path
from uuid import uuid4
from typing import Callable

from hello_agents import HelloAgentsLLM
from hello_agents.tools import ToolRegistry

from ..services.llm_service import create_llm
from ..services.search_service import SearchService
from ..services.notes_service import NotesService
from ..services.tool_registry import ResearchToolManager
from ..models.schemas import SummaryState
from ..config import Configuration
from .research_agents import PlanningService, SummarizationService, ReportingService
from .tool_aware_agent import ToolCallListener

logger = logging.getLogger(__name__)


class ResearchCancelled(RuntimeError):
    """在阶段边界停止研究，已完成的笔记保留。"""


class DeepResearchAgent:
    """共享模型、注册表和监听器；每份研究使用独立实例。"""

    def __init__(self, llm: HelloAgentsLLM | None = None,
                 tool_registry: ToolRegistry | None = None,
                 event_listener: ToolCallListener | None = None,
                 search_service: SearchService | None = None,
                 config: Configuration | None = None,
                 should_stop: Callable[[], bool] | None = None):
        self.config = (config or Configuration.from_env()).model_copy(deep=True)
        self.llm = llm if llm is not None else create_llm()
        self._event_listener = event_listener
        self.search_service = search_service
        # 外部显式提供的注册表按原样使用；默认由管理器注册search与note。
        self.tool_manager = ResearchToolManager(self.config, search_service) if tool_registry is None else None
        self.tool_registry = self.tool_manager.registry if self.tool_manager is not None else tool_registry
        self._run_count = 0
        self._should_stop = should_stop

        def tool_listener(call_info):
            self._emit_event({
                'type': 'tool_call',
                'agent': call_info['agent_name'],
                'tool': call_info['tool_name'],
                'parameters': call_info['parsed_parameters'],
                'result': call_info['result'],
            })

        self.planner = PlanningService(self.llm, tool_listener, self.tool_registry)
        self.summarizer = SummarizationService(self.llm, tool_listener, self.tool_registry)
        self.reporter = ReportingService(self.llm, tool_listener, self.tool_registry)

    def run(self, research_topic: str) -> str:
        if not isinstance(research_topic, str) or not research_topic.strip():
            raise ValueError('研究主题不能为空')
        state = SummaryState(research_topic=research_topic.strip())
        try:
            self._check_cancelled()
            # 每次研究使用独立目录，避免多次运行或不同实例的索引互相覆盖。
            if self.tool_manager is not None:
                notes = (self.tool_manager.start_notes_workspace() if self._run_count
                         else self.tool_manager.notes)
            else:
                notes = NotesService(str(Path(self.config.notes_workspace) / uuid4().hex))
            self._run_count += 1
            self._emit_event({'type': 'notes_workspace', 'path': str(notes.workspace)})
            self._emit_event({'type': 'status', 'stage': 'planning', 'message': '正在规划研究任务...'})
            todo_list = self.planner.plan_todo_list(state)
            self._check_cancelled()
            plan_note_id = notes.save_plan(state.research_topic, todo_list)
            self._emit_event({'type': 'note_saved', 'kind': 'plan', 'note_id': plan_note_id})
            self._emit_event({'type': 'tasks', 'tasks': [asdict(task) for task in todo_list]})
            if self.search_service is None:
                self.search_service = (self.tool_manager.search_tool.service if self.tool_manager is not None
                                       else SearchService(config=self.config))
            task_summaries = []
            for task in todo_list:
                self._check_cancelled()
                self._emit_event({'type': 'task_started', 'task_id': task.id})
                self._emit_event({'type': 'status', 'message': f'正在研究：{task.title}'})
                search_results = self.search_service.search(task.query)
                self._check_cancelled()
                summary, source_urls = self.summarizer.summarize_task(task, search_results)
                note_id = notes.save_task_summary(task, search_results, summary)
                self._emit_event({'type': 'note_saved', 'kind': 'task_summary',
                                  'task_id': task.id, 'note_id': note_id})
                task_summaries.append((task, summary, source_urls))
                self._emit_event({'type': 'task_summary', 'task_id': task.id,
                                  'summary': summary, 'source_urls': source_urls})
                self._emit_event({'type': 'task_completed', 'task_id': task.id})
            self._check_cancelled()
            self._emit_event({'type': 'status', 'stage': 'reporting', 'message': '正在生成报告...'})
            report = self.reporter.generate_report(state.research_topic, task_summaries)
            self._check_cancelled()
            report_note_id = notes.save_report(state.research_topic, report)
            self._emit_event({'type': 'note_saved', 'kind': 'report', 'note_id': report_note_id})
            self._emit_event({'type': 'report', 'content': report})
            return report
        except ResearchCancelled:
            raise
        except Exception:
            self._emit_event({'type': 'error', 'message': '研究未完成，请检查模型、搜索服务或输入资料'})
            raise

    def _check_cancelled(self) -> None:
        if self._should_stop is not None and self._should_stop():
            raise ResearchCancelled('研究已停止')

    def _emit_event(self, event: dict) -> None:
        if self._event_listener is not None:
            try:
                self._event_listener(deepcopy(event))
            except Exception:
                logger.warning('研究事件监听器失败，研究调用继续执行')
