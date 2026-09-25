<template>
  <div v-if="event">
    <!-- Event summary -->
    <div class="card summary">
      <div class="title-row">
        <h2 class="page-title">{{ event.name }}</h2>
        <span class="badge" :class="event.status">{{ statusLabel(event.status) }}</span>
      </div>
      <p class="description">{{ event.description }}</p>
      <div class="details">
        <div class="detail">
          <span class="detail-label">Proposed</span>
          <span>{{ event.proposedDate || "—" }} {{ event.proposedTime || "" }}</span>
        </div>
        <div class="detail">
          <span class="detail-label">Expected attendance</span>
          <span>{{ event.expectedAttendance || "—" }}</span>
        </div>
      </div>
    </div>

    <div v-if="event.clarificationFlag" class="notice">
      <strong>Clarification requested:</strong> {{ event.clarificationComments }}
    </div>

    <div v-if="event.status === 'rejected' && event.reviewDecision?.reason" class="notice error">
      <strong>Rejection reason:</strong> {{ event.reviewDecision.reason }}
    </div>

    <!-- Coordinator Actions: Event Review and Approval + Coordinator Assignment + Event Status Management -->
    <section v-if="isAssignedCoordinator">
      <h3 class="section-title">Coordinator Actions</h3>

      <div v-if="event.status === 'under_review'" class="action-block">
        <textarea v-model="comment" placeholder="Comments / reason"></textarea>
        <div class="actions">
          <button class="btn btn-butter" @click="clarify">Request Clarification</button>
          <button class="btn btn-mint" @click="approve">Approve</button>
          <button class="btn btn-rose" @click="reject">Reject</button>
        </div>
      </div>

      <div v-if="['approved', 'planning'].includes(event.status)" class="action-block">
        <div class="actions">
          <button class="btn btn-rose" @click="cancelEvent">Cancel Event</button>
        </div>
      </div>

      <div v-if="event.status === 'confirmed'" class="action-block">
        <textarea v-model="comment" placeholder="Reason for reverting to planning"></textarea>
        <div class="actions">
          <button class="btn btn-sky" @click="revertToPlanning">
            Revert to Planning (major change)
          </button>
        </div>
      </div>

      <div class="action-block">
        <input v-model.number="newCoordinatorId" type="number" placeholder="New coordinator user ID" />
        <div class="actions">
          <button class="btn btn-primary" @click="reassign">Reassign (after offline agreement)</button>
        </div>
      </div>
    </section>

    <!-- Organiser Actions: Event Review and Approval -->
    <section v-if="isOwningOrganiser">
      <div v-if="event.clarificationFlag" class="action-block">
        <h3 class="block-title">Respond to Clarification</h3>
        <textarea v-model="responseNotes" placeholder="Updated description"></textarea>
        <div class="actions">
          <button class="btn btn-primary" @click="respond">Send Response</button>
        </div>
      </div>

      <div v-if="event.status === 'rejected'" class="action-block">
        <div class="actions">
          <button class="btn btn-primary" @click="resubmit">Revise &amp; Resubmit</button>
        </div>
      </div>
    </section>
  </div>
  <p v-else class="loading">Loading…</p>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import eventsApi from "../api/events";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const event = ref(null);
const comment = ref("");
const responseNotes = ref("");
const newCoordinatorId = ref(null);

// "under_review" -> "under review"
const statusLabel = (status) => (status || "").replace(/_/g, " ");

const isAssignedCoordinator = computed(
  () => auth.hasRole("event_coordinator") && event.value?.coordinatorId === auth.user?.id
);
const isOwningOrganiser = computed(
  () => auth.hasRole("event_organiser") && event.value?.organiserId === auth.user?.id
);

async function load() {
  const { data } = await eventsApi.getEvent(route.params.id);
  event.value = data;
}

async function clarify() {
  await eventsApi.requestClarification(event.value.id, comment.value);
  comment.value = "";
  await load();
}
async function approve() {
  await eventsApi.approveEvent(event.value.id, comment.value);
  comment.value = "";
  await load();
}
async function reject() {
  await eventsApi.rejectEvent(event.value.id, comment.value);
  comment.value = "";
  await load();
}
async function cancelEvent() {
  await eventsApi.changeStatus(event.value.id, "cancelled", comment.value);
  await load();
}
async function revertToPlanning() {
  await eventsApi.changeStatus(event.value.id, "planning", comment.value);
  comment.value = "";
  await load();
}
async function reassign() {
  if (!newCoordinatorId.value) return;
  await eventsApi.reassign(event.value.id, newCoordinatorId.value);
  await load();
}
async function respond() {
  await eventsApi.respondClarification(event.value.id, { description: responseNotes.value });
  responseNotes.value = "";
  await load();
}
async function resubmit() {
  const { data } = await eventsApi.resubmitEvent(event.value.id, {});
  router.push(`/events/${data.id}`);
}

onMounted(load);
</script>

<style scoped>
.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text, #2d2a4a);
}

.section-title {
  margin: 1.5rem 0 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text, #2d2a4a);
}

.block-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text, #2d2a4a);
}

.loading {
  color: var(--text-muted, #6b6890);
}

/* Summary card */
.card {
  padding: 1.25rem 1.5rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #e4defa);
  border-radius: 14px;
  box-shadow: 0 4px 16px rgba(109, 91, 208, 0.08);
}

.title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.75rem;
}

.title-row .badge {
  padding: 0.3rem 0.9rem;
  font-size: 0.95rem;
}

.description {
  margin: 0.75rem 0 1rem;
  line-height: 1.5;
  color: var(--text, #2d2a4a);
}

.details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.7rem 0.9rem;
  border-radius: 12px;
  background: var(--sky-bg, #d6ecff);
  color: var(--sky-text, #1f5f99);
  font-weight: 500;
}

.detail-label {
  font-size: 0.8rem;
  font-weight: 400;
}

/* Status badges */
.badge {
  display: inline-block;
  padding: 0.15rem 0.65rem;
  border-radius: 999px;
  background: var(--lilac-bg, #e9e5fb);
  color: var(--lilac-text, #4b3fa0);
  font-size: 0.8rem;
  font-weight: 500;
  text-transform: capitalize;
  white-space: nowrap;
}

.badge.approved,
.badge.confirmed,
.badge.completed {
  background: var(--mint-bg, #d3f5e3);
  color: var(--mint-text, #1e6b47);
}

.badge.rejected,
.badge.cancelled {
  background: var(--rose-bg, #ffdce3);
  color: var(--rose-text, #a12b47);
}

.badge.under_review,
.badge.submitted {
  background: var(--butter-bg, #fff1c2);
  color: var(--butter-text, #8a5a00);
}

.badge.planning {
  background: var(--sky-bg, #d6ecff);
  color: var(--sky-text, #1f5f99);
}

/* Notices */
.notice {
  margin: 1rem 0;
  padding: 0.85rem 1rem;
  border-radius: 12px;
  background: var(--butter-bg, #fff1c2);
  color: var(--butter-text, #8a5a00);
}

.notice.error {
  background: var(--rose-bg, #ffdce3);
  color: var(--rose-text, #a12b47);
}

/* Action blocks */
.action-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 0.75rem 0 0;
  padding: 1.1rem 1.25rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #e4defa);
  border-radius: 14px;
  box-shadow: 0 4px 16px rgba(109, 91, 208, 0.06);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

textarea,
input {
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border, #e4defa);
  border-radius: 10px;
  background: #fcfbff;
  color: var(--text, #2d2a4a);
  font: inherit;
}

textarea::placeholder,
input::placeholder {
  color: #a5a2c2;
}

textarea:focus,
input:focus {
  outline: none;
  border-color: var(--primary, #6d5bd0);
  background: #ffffff;
  box-shadow: 0 0 0 3px var(--primary-tint, #ebe7ff);
}

textarea {
  min-height: 4.5rem;
  resize: vertical;
}

/* Buttons: colour matches meaning */
.btn {
  padding: 0.5rem 1.1rem;
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

.btn-mint {
  background: var(--mint-bg, #d3f5e3);
  color: var(--mint-text, #1e6b47);
}
.btn-mint:hover {
  background: #bdeed3;
}

.btn-rose {
  background: var(--rose-bg, #ffdce3);
  color: var(--rose-text, #a12b47);
}
.btn-rose:hover {
  background: #ffc9d4;
}

.btn-butter {
  background: var(--butter-bg, #fff1c2);
  color: var(--butter-text, #8a5a00);
}
.btn-butter:hover {
  background: #ffe8a0;
}

.btn-sky {
  background: var(--sky-bg, #d6ecff);
  color: var(--sky-text, #1f5f99);
}
.btn-sky:hover {
  background: #bfe0ff;
}
</style>