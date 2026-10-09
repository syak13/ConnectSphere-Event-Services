<template>
  <div>
    <h2 class="page-title">My Drafts</h2>
    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="drafts.length" class="card">
      <ul class="draft-list">
        <li v-for="d in drafts" :key="d.id">
          <span class="draft-name">{{ d.name || "(untitled)" }}</span>
          <span class="draft-actions">
            <button class="btn btn-sky" @click="editDraft(d.id)">Edit</button>
            <button class="btn btn-primary" @click="submitDraft(d.id)">Submit</button>
            <button class="btn btn-rose" @click="deleteDraft(d.id)">Delete</button>
          </span>
        </li>
      </ul>
    </div>

    <div v-else class="card empty">
      <p>No drafts saved.</p>
    </div>
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

    drafts.value = Array.isArray(data)
      ? data.filter((draft) => draft.status === "draft")
      : [];
  } catch (e) {
    error.value =
      e.response?.data?.error || "Could not load saved drafts.";
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

  const draft = drafts.value.find((item) => item.id === id);

  if (!draft || draft.status !== "draft") {
    error.value = "This item is no longer a draft and cannot be deleted.";
    return;
  }

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
    console.error("Delete draft failed:", {
      status: e.response?.status,
      url: e.config?.url,
      method: e.config?.method,
      response: e.response?.data,
      message: e.message,
    });

    error.value =
      e.response?.data?.error ||
      e.response?.data?.message ||
      `Could not delete this draft (${
        e.response?.status || "unknown error"
      }).`;
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
  flex-wrap: wrap;
  gap: 0.5rem;
}

/* Buttons: colour matches meaning, same as event detail page */
.btn {
  padding: 0.4rem 1rem;
  border: none;
  border-radius: 999px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
}

.btn:focus-visible {
  outline: 2px solid var(--primary, #6d5bd0);
  outline-offset: 2px;
}

.btn-primary {
  background: var(--primary, #6d5bd0);
  color: #ffffff;
}
.btn-primary:hover {
  background: var(--primary-hover, #5b49bd);
}

.btn-sky {
  background: var(--sky-bg, #d6ecff);
  color: var(--sky-text, #1f5f99);
}
.btn-sky:hover {
  background: #bfe0ff;
}

.btn-rose {
  background: var(--rose-bg, #ffdce3);
  color: var(--rose-text, #a12b47);
}
.btn-rose:hover {
  background: #ffc9d4;
}

/* Error message, styled like the other forms */
.error {
  margin: 0 0 1rem;
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
  background: var(--rose-bg, #ffdce3);
  color: var(--rose-text, #a12b47);
  font-size: 0.9rem;
}

/* Empty state */
.empty {
  padding: 2rem 1rem;
  text-align: center;
  color: var(--text-muted, #6b6890);
}

.empty p {
  margin: 0;
}
</style>
