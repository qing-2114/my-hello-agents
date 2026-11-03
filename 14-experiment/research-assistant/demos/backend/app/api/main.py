"""POST + SSE：把同步研究流程放入独立线程，事件实时传给浏览器。"""
import asyncio
import json
from queue import Empty, Full, Queue
from threading import BoundedSemaphore, Event, Thread
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from ..agents.deep_research_agent import DeepResearchAgent, ResearchCancelled
from ..config import Configuration, SearchAPI

app = FastAPI(title='研序 · 深度研究助手')
slots = BoundedSemaphore(2)


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)
    search_api: SearchAPI | None = None

    @field_validator('topic')
    @classmethod
    def topic_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('研究主题不能为空')
        return value.strip()


def encode_sse(event: dict) -> str:
    return 'data: ' + json.dumps(event, ensure_ascii=False) + '\n\n'


class StreamAdapter:
    def __init__(self, send):
        self.send = send
        self.tasks = []
        self.completed = set()

    def progress(self, stage: str, percentage: int, text: str):
        self.send({'type': 'progress', 'stage': stage, 'percentage': percentage, 'text': text})

    def __call__(self, event: dict):
        kind = event['type']
        if kind == 'status':
            if event.get('stage') == 'planning':
                self.progress('planning', 5, event['message'])
            elif event.get('stage') == 'reporting':
                self.progress('reporting', 90, event['message'])
        elif kind == 'tasks':
            self.tasks = event['tasks']
            self.send({'type': 'plan', 'data': self.tasks})
            self.progress('executing', 10, '研究计划已就绪')
        elif kind == 'task_started':
            self.send(event)
            task = next(task for task in self.tasks if task['id'] == event['task_id'])
            self.progress('executing', 10 + int(len(self.completed) / max(1, len(self.tasks)) * 70),
                          f"正在研究 {len(self.completed) + 1}/{len(self.tasks)}：{task['title']}")
        elif kind == 'task_completed':
            self.completed.add(event['task_id'])
            self.send(event)
            self.progress('executing', 10 + int(len(self.completed) / max(1, len(self.tasks)) * 70),
                          f'已完成 {len(self.completed)}/{len(self.tasks)} 个任务')
        elif kind == 'report':
            self.send({'type': 'report', 'data': event['content']})
        elif kind in ('task_summary', 'note_saved'):
            self.send(event)
        elif kind == 'tool_call':
            # 浏览器只需知道工具名；不广播工具参数和原始返回值。
            self.send({'type': 'tool_call', 'agent': event['agent'], 'tool': event['tool']})


async def research_stream(payload: ResearchRequest):
    events = Queue(maxsize=128)
    stop = Event()
    finished = Event()

    def send(event):
        while not stop.is_set():
            try:
                events.put(event, timeout=0.1)
                return
            except Full:
                continue

    def worker():
        try:
            config = Configuration.from_env()
            if payload.search_api is not None:
                config.search_api = payload.search_api
            adapter = StreamAdapter(send)
            DeepResearchAgent(config=config, event_listener=adapter, should_stop=stop.is_set).run(payload.topic)
            adapter.progress('completed', 100, '研究完成')
            send({'type': 'completed'})
        except ResearchCancelled:
            send({'type': 'cancelled'})
        except Exception:
            send({'type': 'error', 'message': '研究未完成。请检查根目录模型与搜索配置，或稍后重试。已保存的任务笔记仍保留。'})
        finally:
            finished.set()
            slots.release()

    thread = Thread(target=worker, name='research-worker', daemon=True)
    try:
        thread.start()
    except Exception:
        slots.release()
        raise
    try:
        yield ': connected\n\n'
        last_heartbeat = time.monotonic()
        while not finished.is_set() or not events.empty():
            try:
                event = events.get_nowait()
            except Empty:
                if time.monotonic() - last_heartbeat >= 10:
                    yield ': heartbeat\n\n'
                    last_heartbeat = time.monotonic()
                await asyncio.sleep(0.05)
                continue
            yield encode_sse(event)
    finally:
        # 断开连接后，在当前网络调用结束的阶段边界停止后续研究。
        stop.set()


@app.get('/healthz')
def health():
    return {'status': 'ok'}


@app.post('/api/research')
async def research(payload: ResearchRequest):
    if not slots.acquire(blocking=False):
        raise HTTPException(429, '研究服务忙，请等待当前任务结束后重试')
    return StreamingResponse(research_stream(payload), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
