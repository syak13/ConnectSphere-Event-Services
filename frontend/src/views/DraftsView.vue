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
import { useRouter } from "vue-router";
import eventsApi from "../api/events";

const drafts = ref([]);
const error = ref("");
const router = useRouter();

async function load() {
  error.value = "";

  try {
    const { data } = await eventsApi.listDrafts();
    drafts.value = data;
  } catch (e) {
    error.value = e.response?.data?.error || "Could not load saved drafts.";
  }
}

function editDraft(id) {
  router.push({ name: "edit-draft", params: { id } });
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
.page-title {
  margin: 0 0 1rem;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text, #2d2a4a);
}

.card {
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #e4defa);
  border-radius: 14px;
  box-shadow: 0 4px 16px rgba(109, 91, 208, 0.08);
  overflow: hidden;
}

.draft-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.draft-list li {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border, #e4defa);
}

.draft-list li:last-child {
  border-bottom: none;
}

.draft-list li:hover {
  background: #faf9ff;
}

.draft-name {
  font-weight: 500;
  color: var(--text, #2d2a4a);
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
