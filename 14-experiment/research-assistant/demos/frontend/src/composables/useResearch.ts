import { reactive, onBeforeUnmount } from "vue";

export interface ResearchTask {
  id: number;
  title: string;
  intent: string;
  query: string;
  status: "pending" | "active" | "completed";
  summary?: string;
  sourceUrls?: string[];
}
export interface ResearchState {
  topic: string;
  isLoading: boolean;
  stage: string;
  progressPercentage: number;
  progressText: string;
  markdownContent: string;
  tasks: ResearchTask[];
  error: string | null;
  completed: boolean;
  cancelled: boolean;
  notesCount: number;
  latestTool: string;
}

export function useResearch() {
  const state = reactive<ResearchState>({
    topic: "",
    isLoading: false,
    stage: "idle",
    progressPercentage: 0,
    progressText: "准备中…",
    markdownContent: "",
    tasks: [],
    error: null,
    completed: false,
    cancelled: false,
    notesCount: 0,
    latestTool: "",
  });
  let controller: AbortController | undefined;
  let requestId = 0;

  function handleEvent(event: Record<string, any>) {
    switch (event.type) {
      case "progress":
        state.progressPercentage = Math.max(
          state.progressPercentage,
          Math.min(100, Math.max(0, Number(event.percentage))),
        );
        state.stage = event.stage;
        state.progressText = event.text;
        break;
      case "plan":
        state.tasks = event.data.map((task: ResearchTask) => ({
          ...task,
          status: "pending",
        }));
        break;
      case "task_started": {
        const task = state.tasks.find((task) => task.id === event.task_id);
        if (task) task.status = "active";
        break;
      }
      case "task_summary": {
        const task = state.tasks.find((task) => task.id === event.task_id);
        if (task) {
          task.summary = event.summary;
          task.sourceUrls = event.source_urls;
        }
        break;
      }
      case "task_completed": {
        const task = state.tasks.find((task) => task.id === event.task_id);
        if (task) task.status = "completed";
        break;
      }
      case "note_saved":
        state.notesCount += 1;
        break;
      case "tool_call":
        state.latestTool = `${event.agent} · ${event.tool}`;
        break;
      case "report":
        state.markdownContent = event.data;
        break;
      case "completed":
        state.completed = true;
        state.isLoading = false;
        break;
      case "error":
        state.error = event.message;
        state.isLoading = false;
        break;
      case "cancelled":
        state.cancelled = true;
        state.isLoading = false;
        break;
    }
  }

  async function startResearch(topic: string, searchApi: string) {
    controller?.abort();
    const id = ++requestId;
    controller = new AbortController();
    const ownController = controller;
    Object.assign(state, {
      topic: topic.trim(),
      isLoading: true,
      stage: "planning",
      progressPercentage: 0,
      progressText: "正在连接研究服务…",
      markdownContent: "",
      tasks: [],
      error: null,
      completed: false,
      cancelled: false,
      notesCount: 0,
      latestTool: "",
    });
    try {
      const response = await fetch("/api/research", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ topic: state.topic, search_api: searchApi }),
        signal: ownController.signal,
      });
      if (!response.ok) {
        if (response.status === 429)
          throw new Error("研究服务忙，请稍后重试。");
        throw new Error(
          `无法启动研究（HTTP ${response.status}），请检查后端服务。`,
        );
      }
      if (!response.body) throw new Error("浏览器未能建立流式连接。");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let dataLines: string[] = [];
      const consumeLine = (line: string) => {
        if (!line) {
          if (dataLines.length) handleEvent(JSON.parse(dataLines.join("\n")));
          dataLines = [];
        } else if (line.startsWith("data:"))
          dataLines.push(line.slice(5).trimStart());
      };
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (id !== requestId) return;
          buffer += decoder.decode(value, { stream: !done });
          let index: number;
          while ((index = buffer.indexOf("\n")) !== -1) {
            consumeLine(buffer.slice(0, index).replace(/\r$/, ""));
            buffer = buffer.slice(index + 1);
          }
          if (done) {
            if (buffer) consumeLine(buffer.replace(/\r$/, ""));
            consumeLine("");
            break;
          }
          if (state.completed || state.error || state.cancelled) {
            await reader.cancel();
            break;
          }
        }
      } finally {
        reader.releaseLock();
      }
      if (!state.completed && !state.error && !state.cancelled)
        throw new Error("连接提前结束，研究未完成。已保存的笔记仍保留。");
    } catch (error) {
      if (id !== requestId) return;
      if ((error as Error).name === "AbortError") state.cancelled = true;
      else
        state.error =
          error instanceof Error ? error.message : "连接失败，请稍后重试。";
    } finally {
      if (id === requestId) state.isLoading = false;
    }
  }

  function cancelResearch() {
    if (!state.isLoading) return;
    state.cancelled = true;
    state.isLoading = false;
    state.progressText = "已停止接收，研究将在当前调用结束后停止";
    controller?.abort();
  }
  onBeforeUnmount(() => {
    ++requestId;
    controller?.abort();
  });
  return { state, startResearch, cancelResearch };
}
