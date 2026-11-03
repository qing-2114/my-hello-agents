<script setup lang="ts">
import { computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

const props = defineProps<{ content: string }>();
const renderedHtml = computed(() => {
  const raw = marked.parse(props.content, {
    breaks: true,
    gfm: true,
    async: false,
  });
  const clean = DOMPurify.sanitize(raw, {
    FORBID_TAGS: ["style", "form", "iframe", "img"],
  });
  const document = new DOMParser().parseFromString(clean, "text/html");
  document.querySelectorAll("a").forEach((link) => {
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  });
  return document.body.innerHTML;
});
</script>

<template><div class="markdown-content" v-html="renderedHtml"></div></template>
