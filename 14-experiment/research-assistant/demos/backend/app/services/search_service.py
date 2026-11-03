"""将 HelloAgents 搜索结果转成总结 Agent 的资料格式。"""
from urllib.parse import urlsplit
import hashlib
import json
import logging
from pathlib import Path
import time
from uuid import uuid4

from dotenv import dotenv_values
from hello_agents.tools import SearchTool
import requests

from ..config import Configuration, ROOT, SearchAPI
from .source_processing import deduplicate_sources, limit_source_tokens

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, config: Configuration | None = None, max_results: int | None = None):
        self.config = (config or Configuration.from_env()).model_copy(deep=True)
        if max_results is not None:
            self.config.max_search_results = max_results
        values = dotenv_values(ROOT / '.env')
        self.backend = self.config.search_api.value
        self.max_results = self.config.max_search_results
        self.cache_dir = Path(self.config.search_cache_dir)
        for backend, key in ((SearchAPI.TAVILY, 'TAVILY_API_KEY'),
                             (SearchAPI.PERPLEXITY, 'PERPLEXITY_API_KEY')):
            if self.config.search_api == backend and not values.get(key):
                raise ValueError(f'{backend.value} 需要根目录 .env 配置 {key}')
        self._tool = SearchTool(
            backend=self.backend, tavily_key=values.get('TAVILY_API_KEY'),
            serpapi_key=values.get('SERPAPI_API_KEY'),
            perplexity_key=values.get('PERPLEXITY_API_KEY'),
        ) if self.config.search_api != SearchAPI.SEARXNG else None

    def search(self, query: str, max_results: int | None = None, use_cache: bool = True) -> list[dict]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError('搜索查询不能为空')
        count = self.max_results if max_results is None else max_results
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 10:
            raise ValueError('搜索结果数量必须在1-10之间')
        query = query.strip()
        cache_file = self.cache_dir / f'{self._generate_cache_key(query, count)}.json'
        if use_cache:
            cached = self._read_cache(cache_file, count)
            if cached is not None:
                logger.info('从缓存读取搜索结果，共%d条', len(cached))
                return cached
        results = self._execute_search(query, count)
        if use_cache:
            self._write_cache(cache_file, results)
        logger.info('搜索成功，共%d条结果', len(results))
        return results

    def _generate_cache_key(self, query: str, max_results: int) -> str:
        content = json.dumps({
            'version': 1, 'query': query.strip(), 'max_results': max_results,
            'backend': self.backend, 'max_tokens_per_source': self.config.max_tokens_per_source,
            'searxng_url': self.config.searxng_url if self.backend == 'searxng' else None,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _read_cache(self, path: Path, count: int) -> list[dict] | None:
        try:
            if self.config.search_cache_ttl_seconds == 0:
                return None
            if time.time() - path.stat().st_mtime > self.config.search_cache_ttl_seconds:
                return None
            results = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(results, list) or not 1 <= len(results) <= count:
                return None
            for source in results:
                if not isinstance(source, dict) or any(
                    not isinstance(source.get(key), str) or not source[key].strip()
                    for key in ('title', 'url', 'snippet')
                ):
                    return None
                url = urlsplit(source['url'])
                if url.scheme not in ('http', 'https') or not url.netloc:
                    return None
                if len(source['snippet']) > self.config.max_tokens_per_source * 4:
                    return None
            if len({source['url'] for source in results}) != len(results):
                return None
            return results
        except (OSError, ValueError):
            return None

    def _write_cache(self, path: Path, results: list[dict]) -> None:
        temporary = path.with_suffix(f'.{uuid4().hex}.tmp')
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(path)
        except OSError:
            logger.warning('搜索缓存写入失败，仍返回实际搜索结果')
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _execute_search(self, query: str, max_results: int) -> list[dict]:
        try:
            payload = self._search_searxng(query) if self._tool is None else self._tool.run({
                'input': query, 'backend': self.backend, 'mode': 'structured',
                'max_results': max_results, 'fetch_full_page': False,
                'max_tokens_per_source': self.config.max_tokens_per_source,
            })
        except Exception:
            raise RuntimeError(f'{self.backend} 搜索失败，请检查搜索服务及配置') from None
        if not isinstance(payload, dict):
            raise RuntimeError('搜索服务没有返回结构化结果')
        sources = []
        for item in payload.get('results') or []:
            if not isinstance(item, dict):
                continue
            title = item.get('title')
            url = item.get('url')
            snippet = item.get('content') or item.get('snippet')
            if not all(isinstance(value, str) and value.strip() for value in (title, url, snippet)):
                continue
            url = url.strip()
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                continue
            sources.append({'title': title.strip(), 'url': url, 'snippet': snippet.strip()})
        if not sources:
            raise RuntimeError('搜索未返回有效资料，停止研究以避免无依据总结')
        return [limit_source_tokens(source, self.config.max_tokens_per_source)
                for source in deduplicate_sources(sources)[:max_results]]

    def _search_searxng(self, query: str) -> dict:
        # SDK从进程环境读取URL；这里直接使用实例配置，避免修改全局环境。
        endpoint = self.config.searxng_url.rstrip('/') + '/search'
        response = requests.get(endpoint, params={
            'q': query, 'format': 'json', 'language': 'zh-CN',
            'safesearch': 1, 'categories': 'general',
        }, timeout=10)
        response.raise_for_status()
        return response.json()
