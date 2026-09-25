<template>
  <div>
    <h2 class="page-title">My Drafts</h2>

    <div v-if="drafts.length" class="card">
      <ul class="draft-list">
        <li v-for="d in drafts" :key="d.id">
          <span class="draft-name">{{ d.name || "(untitled)" }}</span>
          <span class="draft-actions">
            <button class="btn-submit" @click="submitDraft(d.id)">Submit</button>
            <button class="btn-delete" @click="deleteDraft(d.id)">Delete</button>
          </span>
        </li>
      </ul>
    </div>

    <div v-else class="card empty">
      <p>No drafts saved.</p>
      <router-link to="/events/new" class="btn">Start a new request</router-link>
    </div>
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
  if (!window.confirm("Delete this draft? This can't be undone.")) return;
  await eventsApi.deleteDraft(id);
  await load();
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

/* Buttons */
.btn-submit,
.btn-delete,
.btn {
  padding: 0.4rem 1rem;
  border: none;
  border-radius: 999px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
}

.btn-submit,
.btn {
  background: var(--primary, #6d5bd0);
  color: #ffffff;
}

.btn-submit:hover,
.btn:hover {
  background: var(--primary-hover, #5b49bd);
}

.btn-delete {
  background: var(--rose-bg, #ffdce3);
  color: var(--rose-text, #a12b47);
}

.btn-delete:hover {
  background: #ffc9d4;
}

.btn-submit:focus-visible,
.btn-delete:focus-visible,
.btn:focus-visible {
  outline: 2px solid var(--primary, #6d5bd0);
  outline-offset: 2px;
}

/* Empty state */
.empty {
  padding: 2rem 1rem;
  text-align: center;
  color: var(--text-muted, #6b6890);
}

.empty p {
  margin: 0 0 1rem;
}

.empty .btn {
  display: inline-block;
}
</style>