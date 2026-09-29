<template>
  <div v-if="event">
    <h2>{{ event.name }}</h2>
    <p>Status: <span class="badge" :class="event.status">{{ event.status }}</span></p>
    <p>{{ event.description }}</p>
    <p>Proposed: {{ event.proposedDate || "—" }} {{ event.proposedTime || "" }}</p>
    <p>Expected attendance: {{ event.expectedAttendance || "—" }}</p>
    <p>Requested by: {{ event.organiserName || "—" }}</p>
    <p v-if="event.coordinatorId">Coordinator: {{ event.coordinatorName }}</p>

    <div v-if="!event.coordinatorId" class="notice">
      <strong>Unassigned.</strong> No Coordinator is currently assigned to this event.
    </div>

    <section class="detail-block">
      <h3>Venue Requirements</h3>
      <ul>
        <li>Capacity needed: {{ event.venueRequirements?.capacityNeeded ?? "—" }}</li>
        <li>Required layout: {{ event.venueRequirements?.requiredLayout || "—" }}</li>
        <li>Accessibility needs: {{ event.venueRequirements?.accessibilityNeeds || "—" }}</li>
        <li v-if="event.venueRequirements?.requiredFacilities?.length">
          Required facilities: {{ event.venueRequirements.requiredFacilities.join(", ") }}
        </li>
      </ul>
    </section>

    <section class="detail-block" v-if="event.equipmentRequirements?.length">
      <h3>Equipment Requirements</h3>
      <ul>
        <li v-for="eq in event.equipmentRequirements" :key="eq.id">
          {{ eq.quantity }}× {{ eq.type }}
          <span v-if="eq.technicalNotes">— {{ eq.technicalNotes }}</span>
          (<span class="badge" :class="eq.status">{{ eq.status }}</span>)
        </li>
      </ul>
    </section>

    <div v-if="event.clarificationFlag" class="notice">
      <strong>Clarification requested:</strong> {{ event.clarificationComments }}
    </div>

    <div v-if="event.status === 'rejected' && event.reviewDecision.reason" class="notice error">
      <strong>Rejection reason:</strong> {{ event.reviewDecision.reason }}
    </div>

    <!-- Coordinator Assignment: visible to any Coordinator when the event has
         no assigned Coordinator yet. Still fully rule-based — the caller
         doesn't pick who it goes to, they just trigger the automatic retry
         (see try_assign_and_advance). Not gated by isAssignedCoordinator
         since, by definition, nobody is assigned yet. -->
    <section v-if="auth.hasRole('event_coordinator') && !event.coordinatorId && event.status === 'submitted'">
      <div class="action-block">
        <p>No Coordinator was available when this was submitted.</p>
        <button @click="autoAssign">Assign a Coordinator now</button>
      </div>
    </section>

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
        <label>
          Reassign to
          <select v-model.number="newCoordinatorId">
            <option disabled :value="null">Select a coordinator</option>
            <option v-for="c in otherCoordinators" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
        <button :disabled="!newCoordinatorId" @click="reassign">Reassign (after offline agreement)</button>
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
import usersApi from "../api/users";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const event = ref(null);
const comment = ref("");
const responseNotes = ref("");
const newCoordinatorId = ref(null);
const coordinators = ref([]);

const isAssignedCoordinator = computed(
  () => auth.hasRole("event_coordinator") && event.value?.coordinatorId === auth.user?.id
);
const isOwningOrganiser = computed(
  () => auth.hasRole("event_organiser") && event.value?.organiserId === auth.user?.id
);
// Exclude yourself — reassigning "to" the coordinator who already owns it is a no-op the backend rejects anyway.
const otherCoordinators = computed(() => coordinators.value.filter((c) => c.id !== auth.user?.id));

async function load() {
  const { data } = await eventsApi.getEvent(route.params.id);
  event.value = data;
}

async function loadCoordinators() {
  const { data } = await usersApi.listCoordinators();
  coordinators.value = data;
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
  newCoordinatorId.value = null;
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
async function autoAssign() {
  await eventsApi.autoAssign(event.value.id);
  await load();
}

onMounted(async () => {
  await load();
  // /auth/users is coordinator-only server-side; only fetch it if this
  // viewer actually has that role, to avoid a needless 403.
  if (auth.hasRole("event_coordinator")) {
    await loadCoordinators();
  }
});
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
.detail-block {
  margin: 1rem 0;
  padding: 1rem;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 6px;
}
.detail-block h3 {
  margin-top: 0;
}
.detail-block ul {
  margin: 0;
  padding-left: 1.25rem;
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
