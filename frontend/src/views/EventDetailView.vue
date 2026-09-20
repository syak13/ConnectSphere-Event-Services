<template>
  <div v-if="event">
    <h2>{{ event.name }}</h2>
    <p>Status: <span class="badge" :class="event.status">{{ event.status }}</span></p>
    <p>{{ event.description }}</p>
    <p>Proposed: {{ event.proposedDate || "—" }} {{ event.proposedTime || "" }}</p>
    <p>Expected attendance: {{ event.expectedAttendance || "—" }}</p>

    <div v-if="event.clarificationFlag" class="notice">
      <strong>Clarification requested:</strong> {{ event.clarificationComments }}
    </div>

    <div v-if="event.status === 'rejected' && event.reviewDecision.reason" class="notice error">
      <strong>Rejection reason:</strong> {{ event.reviewDecision.reason }}
    </div>

    <!-- Coordinator Actions: Event Review and Approval + Coordinator Assignment + Event Status Management -->
    <section v-if="isAssignedCoordinator">
      <h3>Coordinator Actions</h3>

      <div v-if="event.status === 'under_review'" class="action-block">
        <textarea v-model="comment" placeholder="Comments / reason"></textarea>
        <div class="actions">
          <button @click="clarify">Request Clarification</button>
          <button @click="approve">Approve</button>
          <button @click="reject">Reject</button>
        </div>
      </div>

      <div v-if="['approved', 'planning'].includes(event.status)" class="action-block">
        <button @click="cancelEvent">Cancel Event</button>
      </div>

      <div v-if="event.status === 'confirmed'" class="action-block">
        <textarea v-model="comment" placeholder="Reason for reverting to planning"></textarea>
        <button @click="revertToPlanning">Revert to Planning (major change)</button>
      </div>

      <div class="action-block">
        <input v-model.number="newCoordinatorId" type="number" placeholder="New coordinator user ID" />
        <button @click="reassign">Reassign (after offline agreement)</button>
      </div>
    </section>

    <!-- Organiser Actions: Event Review and Approval -->
    <section v-if="isOwningOrganiser">
      <div v-if="event.clarificationFlag" class="action-block">
        <h3>Respond to Clarification</h3>
        <textarea v-model="responseNotes" placeholder="Updated description"></textarea>
        <button @click="respond">Send Response</button>
      </div>

      <div v-if="event.status === 'rejected'" class="action-block">
        <button @click="resubmit">Revise &amp; Resubmit</button>
      </div>
    </section>
  </div>
  <p v-else>Loading…</p>
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
.badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: #eee;
  font-size: 0.8rem;
  text-transform: capitalize;
}
.badge.approved, .badge.confirmed { background: #d7f5dd; }
.badge.rejected, .badge.cancelled { background: #fbdcdc; }
.badge.under_review, .badge.planning { background: #fff3cd; }
.notice {
  background: #fff8e1;
  padding: 0.75rem;
  border-radius: 4px;
  margin: 1rem 0;
}
.notice.error {
  background: #fbdcdc;
}
.action-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 1rem 0;
  padding: 1rem;
  background: #fff;
  border: 1px solid #eee;
  border-radius: 6px;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
textarea, input {
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
textarea {
  min-height: 4rem;
}
</style>
