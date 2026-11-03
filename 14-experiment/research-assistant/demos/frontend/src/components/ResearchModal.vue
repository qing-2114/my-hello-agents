<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import type { ResearchState } from "../composables/useResearch";
import MarkdownContent from "./MarkdownContent.vue";

const props = defineProps<{ isOpen: boolean; state: ResearchState }>();
const emit = defineEmits<{ close: []; cancel: []; retry: [] }>();
const dialog = ref<HTMLDialogElement>();
const readingScroll = ref<HTMLElement>();
const view = ref<"process" | "report">("process");
const selectedTask = ref<number | null>(null);
let previousOverflow: string | undefined;
const completedCount = computed(
  () => props.state.tasks.filter((task) => task.status === "completed").length,
);
const selected = computed(() =>
  props.state.tasks.find((task) => task.id === selectedTask.value),
);
const status = computed(() =>
  props.state.error
    ? "研究遇到问题"
    : props.state.cancelled
      ? "研究已停止"
      : props.state.completed
        ? "研究已完成"
        : "研究进行中",
);
const sourcesCount = computed(
  () =>
    new Set(props.state.tasks.flatMap((task) => task.sourceUrls ?? [])).size,
);

function unlockScroll() {
  if (previousOverflow !== undefined) {
    document.body.style.overflow = previousOverflow;
    previousOverflow = undefined;
  }
}
watch(
  () => props.isOpen,
  async (open) => {
    await nextTick();
    if (open && props.isOpen && !dialog.value?.open) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      dialog.value?.showModal();
    } else if (!props.isOpen) {
      dialog.value?.close();
      unlockScroll();
    }
  },
  { immediate: true },
);
watch(
  () => props.state.markdownContent,
  (content) => {
    if (content) view.value = "report";
  },
);
watch(
  () => props.state.topic,
  () => {
    view.value = "process";
    selectedTask.value = null;
  },
);
watch(
  () => props.state.isLoading,
  (loading, wasLoading) => {
    if (loading && !wasLoading) {
      view.value = "process";
      selectedTask.value = null;
    }
  },
);
watch([view, selectedTask, () => props.state.markdownContent], async () => {
  await nextTick();
  readingScroll.value?.scrollTo({ top: 0 });
});
onBeforeUnmount(() => {
  dialog.value?.close();
  unlockScroll();
});

function downloadReport() {
  const url = URL.createObjectURL(
    new Blob([props.state.markdownContent], {
      type: "text/markdown;charset=utf-8",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${props.state.topic.replace(/[\\/:*?"<>|]/g, "_").slice(0, 60) || "研究报告"}.md`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
</script>

<template>
  <dialog
    ref="dialog"
    class="research-dialog"
    aria-labelledby="research-title"
    @cancel.prevent="emit('close')"
    @click.self="emit('close')"
  >
    <section class="modal-container">
      <header class="modal-header">
        <div class="modal-heading">
          <span class="eyebrow"
            ><span
              class="live-dot"
              :class="{ pulsing: state.isLoading }"
            ></span>
            RESEARCH WORKSPACE</span
          >
          <h2 id="research-title">{{ state.topic }}</h2>
        </div>
        <button
          class="icon-button close-button"
          aria-label="关闭研究窗口"
          autofocus
          @click="emit('close')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 6 12 12M18 6 6 18" />
          </svg>
        </button>
      </header>

      <section class="progress-section" aria-label="研究进度">
        <div class="progress-label">
          <span role="status">{{ state.progressText }}</span
          ><strong>{{ state.progressPercentage }}<small>%</small></strong>
        </div>
        <div
          class="progress-bar"
          role="progressbar"
          aria-label="研究阶段进度"
          :aria-valuenow="state.progressPercentage"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <div
            class="progress-fill"
            :style="{ width: state.progressPercentage + '%' }"
          ></div>
        </div>
        <div class="stage-labels">
          <span :class="{ active: state.stage === 'planning' }"
            >01 规划问题</span
          ><span :class="{ active: state.stage === 'executing' }"
            >02 检索与分析</span
          ><span
            :class="{
              active: ['reporting', 'completed'].includes(state.stage),
            }"
            >03 整合报告</span
          >
        </div>
      </section>

      <div class="workspace-body">
        <aside class="task-sidebar" aria-label="研究任务">
          <div class="sidebar-heading">
            <h3>研究路径</h3>
            <span>{{ completedCount }} / {{ state.tasks.length || "—" }}</span>
          </div>
          <p class="sidebar-hint">从问题出发，沿证据深入。</p>
          <div v-if="!state.tasks.length" class="planning-placeholder">
            <span class="spinner" v-if="state.isLoading"></span>
            <p>
              {{
                state.isLoading ? "正在拆解你的研究问题" : "尚未生成研究计划"
              }}
            </p>
          </div>
          <ol v-else class="task-list">
            <li v-for="task in state.tasks" :key="task.id">
              <button
                class="task-card"
                :class="{
                  selected: selectedTask === task.id && view === 'process',
                  running: task.status === 'active' && state.isLoading,
                  done: task.status === 'completed',
                }"
                @click="
                  selectedTask = task.id;
                  view = 'process';
                "
              >
                <span class="task-number"
                  ><span v-if="task.status === 'completed'">✓</span
                  ><span v-else>{{
                    String(task.id).padStart(2, "0")
                  }}</span></span
                >
                <span class="task-copy"
                  ><strong>{{ task.title }}</strong
                  ><span>{{
                    task.status === "completed"
                      ? "已完成 · 点击查看"
                      : task.status === "active"
                        ? state.cancelled
                          ? "已停止"
                          : state.error
                            ? "已中断"
                            : "正在研究"
                        : "等待执行"
                  }}</span></span
                >
                <span
                  v-if="task.status === 'active' && state.isLoading"
                  class="tiny-spinner"
                  aria-hidden="true"
                ></span>
              </button>
            </li>
          </ol>
          <div class="sidebar-bottom">
            <span class="small-label">已收集的资料</span
            ><strong>{{ sourcesCount }}<small> 个独立来源</small></strong
            ><span>每一条发现，都应有迹可循。</span>
          </div>
        </aside>

        <section class="reading-panel" aria-label="研究内容">
          <nav class="content-tabs" aria-label="研究视图">
            <button
              :class="{ active: view === 'process' }"
              @click="view = 'process'"
            >
              研究过程
            </button>
            <button
              :class="{ active: view === 'report' }"
              :disabled="!state.markdownContent"
              @click="view = 'report'"
            >
              最终报告<span
                v-if="state.markdownContent"
                class="ready-dot"
              ></span>
            </button>
            <span class="reading-label">{{
              view === "report" ? "RESEARCH REPORT" : "RESEARCH NOTES"
            }}</span>
          </nav>
          <div ref="readingScroll" class="reading-scroll">
            <div v-if="state.error" class="error-card" role="alert">
              <strong>这次研究暂时中断了</strong>
              <p>{{ state.error }}</p>
              <button class="text-button" @click="emit('retry')">
                重新研究 <span>↗</span>
              </button>
            </div>
            <div v-if="state.cancelled" class="notice-card" role="status">
              研究已停止。已完成的任务内容仍可查看；后端会在当前调用结束后停止后续步骤。
            </div>

            <MarkdownContent
              v-if="view === 'report' && state.markdownContent"
              :content="state.markdownContent"
            />
            <template v-else-if="selected">
              <div class="note-heading">
                <span class="eyebrow"
                  >TASK {{ String(selected.id).padStart(2, "0") }}</span
                >
                <h2>{{ selected.title }}</h2>
                <p>{{ selected.intent }}</p>
              </div>
              <div class="query-block">
                <span>检索方向</span><code>{{ selected.query }}</code>
              </div>
              <MarkdownContent
                v-if="selected.summary"
                :content="selected.summary"
              />
              <div v-else class="task-waiting">
                <span
                  v-if="selected.status === 'active' && state.isLoading"
                  class="spinner"
                ></span>
                <p>
                  {{
                    selected.status === "active" && state.isLoading
                      ? "正在检索资料并提炼关键发现…"
                      : "此任务暂未生成总结。"
                  }}
                </p>
              </div>
            </template>
            <template v-else>
              <div class="process-intro">
                <span class="eyebrow">A QUESTION, WELL EXPLORED.</span>
                <h2>让证据逐步<br />成为答案。</h2>
                <p>
                  规划研究路径，检索相关资料，<br />将分散的信息整理为可追溯的发现。
                </p>
              </div>
              <div class="process-map">
                <div :class="{ reached: state.stage !== 'idle' }">
                  <span>01</span><strong>拆解问题</strong>
                  <p>明确方向与研究意图</p>
                </div>
                <div :class="{ reached: state.tasks.length > 0 }">
                  <span>02</span><strong>寻找证据</strong>
                  <p>检索、阅读与提炼</p>
                </div>
                <div :class="{ reached: !!state.markdownContent }">
                  <span>03</span><strong>形成洞见</strong>
                  <p>整合为结构化报告</p>
                </div>
              </div>
              <div class="live-message" role="status">
                <span v-if="state.isLoading" class="tiny-spinner"></span
                ><span>{{
                  state.isLoading ? state.progressText : status
                }}</span>
              </div>
              <p class="selection-hint" v-if="state.tasks.length">
                选择左侧任务，查看研究目标与阶段总结。
              </p>
            </template>
          </div>
        </section>
      </div>

      <footer class="modal-footer">
        <div class="footer-status">
          <span
            class="live-dot"
            :class="{ muted: state.error || state.cancelled }"
          ></span
          ><span>{{ status }}</span
          ><span class="footer-divider"></span
          ><span>{{ state.notesCount }} 条笔记已保存</span>
        </div>
        <div class="footer-actions">
          <button
            v-if="state.isLoading"
            class="quiet-button"
            @click="emit('cancel')"
          >
            停止研究</button
          ><button
            v-if="state.markdownContent"
            class="primary-button compact"
            @click="downloadReport"
          >
            下载 Markdown <span>↓</span></button
          ><span v-else class="escape-hint">Esc 收起窗口</span>
        </div>
      </footer>
    </section>
  </dialog>
</template>
