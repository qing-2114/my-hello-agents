<script setup lang="ts">
import { ref } from "vue";
import ResearchModal from "./components/ResearchModal.vue";
import { useResearch } from "./composables/useResearch";

const topic = ref("");
const searchApi = ref("tavily");
const isOpen = ref(false);
const { state, startResearch, cancelResearch } = useResearch();
const examples = [
  "Python asyncio 的适用场景与工程实践",
  "多模态大模型的技术进展与应用",
  "RAG 与长上下文的优势、限制及选型",
];
function start() {
  if (!topic.value.trim() || state.isLoading) return;
  isOpen.value = true;
  void startResearch(topic.value, searchApi.value);
}
function retry() {
  void startResearch(state.topic, searchApi.value);
}
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <a href="/" class="brand" aria-label="研序首页"
        ><span class="brand-symbol">研</span
        ><span>研序<small>RESEARCH STUDIO</small></span></a
      ><span class="header-note"
        ><span class="live-dot"></span> 从提问到洞见</span
      >
    </header>
    <main class="landing-main">
      <section class="hero">
        <div class="hero-label">
          <span class="fine-line"></span> YOUR PERSONAL RESEARCH DESK
        </div>
        <h1>一个好问题，<br />值得一次<span>深入研究。</span></h1>
        <p class="hero-description">
          把好奇交给研究助手。拆解问题、寻找证据，<br />让每一个结论都有来源，让复杂信息有条理。
        </p>
      </section>

      <section class="research-entry" aria-labelledby="entry-title">
        <form @submit.prevent="start">
          <label id="entry-title" for="topic"
            >今天，你想深入了解什么？<span>RESEARCH BRIEF</span></label
          >
          <textarea
            id="topic"
            v-model="topic"
            maxlength="1000"
            rows="3"
            :disabled="state.isLoading"
            placeholder="描述你的研究主题，也可以加入关注角度、时间范围或具体问题…"
            required
          ></textarea>
          <div class="entry-bottom">
            <div class="search-select">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="10.5" cy="10.5" r="6.5" />
                <path d="m16 16 4 4" /></svg
              ><label for="search-api" class="sr-only">搜索服务</label
              ><select
                id="search-api"
                v-model="searchApi"
                :disabled="state.isLoading"
              >
                <option value="tavily">Tavily 搜索</option>
                <option value="duckduckgo">DuckDuckGo 搜索</option>
                <option value="advanced">自动回退搜索</option>
                <option value="perplexity">Perplexity 搜索</option>
                <option value="searxng">SearXNG 搜索</option>
              </select>
            </div>
            <button
              class="primary-button"
              type="submit"
              :disabled="!topic.trim() || state.isLoading"
            >
              {{ state.isLoading ? "正在研究" : "开始深度研究"
              }}<svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14m-5-5 5 5-5 5" />
              </svg>
            </button>
          </div>
        </form>
        <div class="example-topics">
          <span>试着问问</span
          ><button
            v-for="example in examples"
            :key="example"
            :disabled="state.isLoading"
            @click="topic = example"
          >
            {{ example }} <span>↗</span>
          </button>
        </div>
      </section>

      <button v-if="state.topic" class="resume-card" @click="isOpen = true">
        <span class="live-dot" :class="{ pulsing: state.isLoading }"></span
        ><span
          >{{
            state.isLoading
              ? "研究进行中"
              : state.completed
                ? "查看研究报告"
                : "查看本次研究"
          }}<small>{{ state.topic }}</small></span
        ><span>打开工作台 ↗</span>
      </button>

      <section class="capabilities" aria-label="研究工作方式">
        <div>
          <span>01 / PLAN</span>
          <h3>有方向地探索</h3>
          <p>将复杂主题拆成清晰的研究任务。</p>
        </div>
        <div>
          <span>02 / DISCOVER</span>
          <h3>让发现有依据</h3>
          <p>汇集资料，保留每一条来源引用。</p>
        </div>
        <div>
          <span>03 / SYNTHESIZE</span>
          <h3>将信息变为洞见</h3>
          <p>整合分析，生成可阅读的研究报告。</p>
        </div>
      </section>
    </main>
    <footer class="site-footer">
      <span>保持好奇，认真求证。</span
      ><a
        href="https://hello-agents.datawhale.cc/"
        target="_blank"
        rel="noopener noreferrer"
        >基于 Datawhale · Hello Agents 学习实践 ↗</a
      >
    </footer>
    <ResearchModal
      :is-open="isOpen"
      :state="state"
      @close="isOpen = false"
      @cancel="cancelResearch"
      @retry="retry"
    />
  </div>
</template>
