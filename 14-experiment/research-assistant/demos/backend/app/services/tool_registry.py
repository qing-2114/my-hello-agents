"""为研究角色统一管理 search 与 note 工具。"""
import json
from pathlib import Path
from uuid import uuid4

from hello_agents.tools import Tool, ToolParameter, ToolRegistry

from ..config import Configuration
from .notes_service import NotesService
from .search_service import SearchService


class ResearchSearchTool(Tool):
    """通过现有SearchService使用SDK SearchTool，统一去重和摘要预算。"""

    def __init__(self, config: Configuration, search_service: SearchService | None = None):
        super().__init__('search', '搜索互联网资料，返回标题、URL与摘要的JSON数组')
        self.config = config.model_copy(deep=True)
        self._service = search_service

    @property
    def service(self) -> SearchService:
        if self._service is None:
            self._service = SearchService(config=self.config)
        return self._service

    def get_parameters(self):
        return [ToolParameter(name='query', type='string', description='搜索关键词')]

    def run(self, parameters: dict) -> str:
        query = parameters.get('query') or parameters.get('input')
        if not isinstance(query, str) or not query.strip():
            raise ValueError('搜索工具需要非空query')
        return json.dumps(self.service.search(query), ensure_ascii=False)


class ResearchToolManager:
    """一个研究实例持有一个注册表和当前笔记服务，顺序使用。"""

    def __init__(self, config: Configuration, search_service: SearchService | None = None):
        self.config = config.model_copy(deep=True)
        self.registry = ToolRegistry()
        self.search_tool = ResearchSearchTool(self.config, search_service)
        self.registry.register_tool(self.search_tool)
        self.start_notes_workspace()

    def start_notes_workspace(self) -> NotesService:
        self.notes = NotesService(str(Path(self.config.notes_workspace) / uuid4().hex))
        # 使用相同名称更新当前会话的note；三个Agent仍持有同一个注册表。
        self.registry.register_tool(self.notes.note_tool, auto_expand=False)
        return self.notes
