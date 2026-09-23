<template>
  <div>
    <h2>My Drafts</h2>
    <p v-if="error" class="error">{{ error }}</p>
    <ul v-if="drafts.length" class="draft-list">
      <li v-for="d in drafts" :key="d.id">
        <span>{{ d.name || "(untitled)" }}</span>
        <span class="draft-actions">
          <button @click="editDraft(d.id)">Edit</button>
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
const error = ref("");

async function load() {
  error.value = "";

  try {
    const { data } = await eventsApi.listDrafts();
    drafts.value = data;
  } catch (e) {
    error.value = e.response?.data?.error || "Could not load saved drafts.";
  }
}

async function submitDraft(id) {
  error.value = "";
  try {
    await eventsApi.submitEvent(id);
    await load();
  } catch (e) {
    error.value =
      e.response?.data?.error ||
      "Could not submit this draft. Please check the required fields.";
  }
}

async function deleteDraft(id) {
  error.value = "";

  const confirmed = window.confirm(
    "Delete this draft? This action cannot be undone."
  );

  if (!confirmed) {
    return;
  }

  try {
    await eventsApi.deleteDraft(id);
    await load();
  } catch (e) {
    error.value = e.response?.data?.error || "Could not delete this draft.";
  }
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
.error {
  color: #b00020;
  margin: 0.5rem 0;
}
</style>
