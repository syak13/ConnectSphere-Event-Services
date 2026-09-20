<template>
  <div>
    <h2>My Drafts</h2>
    <ul v-if="drafts.length" class="draft-list">
      <li v-for="d in drafts" :key="d.id">
        <span>{{ d.name || "(untitled)" }}</span>
        <span class="draft-actions">
          <button @click="submitDraft(d.id)">Submit</button>
          <button @click="deleteDraft(d.id)">Delete</button>
        </span>
      </li>
    </ul>
    <p v-else>No drafts saved.</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import eventsApi from "../api/events";

const drafts = ref([]);

async function load() {
  const { data } = await eventsApi.listDrafts();
  drafts.value = data;
}

async function submitDraft(id) {
  await eventsApi.submitEvent(id);
  await load();
}

async function deleteDraft(id) {
  await eventsApi.deleteDraft(id);
  await load();
}

onMounted(load);
</script>

<style scoped>
.draft-list {
  list-style: none;
  padding: 0;
}
.draft-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  border-bottom: 1px solid #eee;
}
.draft-actions {
  display: flex;
  gap: 0.5rem;
}
</style>
