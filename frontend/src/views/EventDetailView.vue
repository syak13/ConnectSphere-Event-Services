<template>
  <div v-if="event">
    <div v-if="isOwningOrganiser && canRespondToClarifications && openClarifications.length" class="notice">
      <strong>
        {{ openClarifications.length }} clarification request<span v-if="openClarifications.length > 1">s</span>
        awaiting your response.
      </strong>
    </div>

    <div v-if="!event.coordinatorId" class="notice">
      <strong>Unassigned.</strong> No Coordinator is currently assigned to this event.
    </div>

    <div v-if="priorDecisions.length" class="card history">
      <h3 class="section-title">Previous Submission History</h3>
      <p class="notice-inline">
        This is resubmission #{{ priorDecisions.length + 1 }}. Earlier attempts are shown below for reference.
      </p>
      <ul class="thread-list">
        <li v-for="decision in priorDecisions" :key="decision.eventId" class="thread-item">
          <div class="thread-message" :class="decision.outcome">
            <span class="thread-meta">
              {{ decision.outcome === "approved" ? "Approved" : "Rejected" }} by
              {{ decision.coordinatorName || `Coordinator #${decision.coordinatorId}` }}
              · {{ formatDate(decision.timestamp) }}
            </span>
            <p v-if="decision.reason">{{ decision.reason }}</p>
          </div>
        </li>
      </ul>
    </div>

    <!-- Event summary -->
    <div class="card summary">
      <div class="title-row">
        <h2 class="page-title">{{ event.name }}</h2>
        <span class="badge" :class="event.status">{{ statusLabel(event.status) }}</span>
      </div>
      <div v-if="event.reviewDecision?.outcome" class="notice" :class="event.reviewDecision.outcome">
        <strong>
          {{ event.reviewDecision.outcome === "approved" ? "Request approved" : "Request rejected" }}
        </strong>
        <p class="decision-meta">
          By {{ event.reviewDecision.coordinatorName || `Coordinator #${event.reviewDecision.coordinatorId}` }}
          on {{ formatDate(event.reviewDecision.timestamp) }}
        </p>
        <p v-if="event.reviewDecision.reason" class="decision-reason">
          <strong>Reason:</strong> {{ event.reviewDecision.reason }}
        </p>
      </div>
      <p class="description">{{ event.description }}</p>
      <div class="details">
        <div class="detail">
          <span class="detail-label">Proposed Date and Time</span>
          <span>{{ event.proposedDate || "—" }} {{ event.proposedTime || "" }}</span>
        </div>
        <div class="detail">
          <span class="detail-label">Expected attendance</span>
          <span>{{ event.expectedAttendance || "—" }}</span>
        </div>
        <div class="detail">
          <span class="detail-label">Equipment required</span>
          <span>{{ event.venueRequirements?.capacityNeeded || "—" }}</span>
        </div>
        <div class="detail">
          <span class="detail-label">Venue Required</span>
          <span>{{ event.venueRequirements?.requiredLayout || "—" }}</span>
        </div>
        <div class="detail">
          <span class="detail-label">Registration</span>
          <span class="reg-pill" :class="{ required: event.registrationRequired }">
            {{ event.registrationRequired ? "Required" : "Not required" }}
          </span>
        </div>
      </div>

      <div class="accessibility">
        <span class="detail-label">Accessibility needs</span>
        <p>{{ event.venueRequirements?.accessibilityNeeds || "None specified" }}</p>
      </div>
    </div>

    <div>
      <p></p>
    </div>

    <div v-if="clarificationThread.length" class="card history">
      <h3 class="section-title">Clarification Thread</h3>
      <ul class="thread-list">
        <li v-for="item in clarificationThread" :key="item.reviewId" class="thread-item">
          <div class="thread-message request">
            <span class="thread-meta">Coordinator · {{ formatDate(item.request.createdAt) }}</span>
            <p>{{ item.request.comments }}</p>
            <p v-if="item.request.editableFields?.length" class="thread-fields">
              Fields opened for editing: {{ formatFieldNames(item.request.editableFields) }}
            </p>
          </div>
          <div v-if="item.response" class="thread-message response">
              <span class="thread-meta">Organiser · {{ formatDate(item.response.createdAt) }}</span>
              <p>{{ item.response.comments }}</p>
              <p v-if="Object.keys(item.response.updatedFields || {}).length" class="thread-fields">
                Updated: {{ formatFieldNames(Object.keys(item.response.updatedFields)) }}
              </p>
            </div>
            <div v-else-if="item.withdrawn" class="thread-withdrawn">Withdrawn by coordinator</div>
            <div v-else class="thread-pending">
              <span>Awaiting organiser's response</span>
              <button
                v-if="isAssignedCoordinator"
                class="btn btn-grey btn-small"
                @click="deleteClarificationRequest(item.reviewId)"
              >
                Delete request
              </button>
            </div>
        </li>
      </ul>

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
      <h3 class="section-title">Coordinator Actions</h3>

      <div v-if="event.status === 'under_review'" class="action-block">
  <textarea v-model="comment" placeholder="Comments / reason"></textarea>

  <div class="field-select">
    <span class="detail-label">Allow organiser to edit:</span>
    <div class="checkbox-grid">
      <label v-for="opt in EDITABLE_FIELD_OPTIONS" :key="opt.key" class="checkbox-option">
        <input type="checkbox" :value="opt.key" v-model="editableFields" />
        {{ opt.label }}
      </label>
    </div>
  </div>

  <div v-if="event.clarificationFlag" class="notice">
    <strong>Clarification requested:</strong> {{ event.clarificationComments }}
    <div v-if="event.clarificationEditableFields?.length" class="editable-fields-note">
      Organiser can edit: {{ formatFieldNames(event.clarificationEditableFields) }}
    </div>
  </div>

  <p v-if="clarificationError" class="field-error">{{ clarificationError }}</p>
  <div class="actions">
    <button class="btn btn-butter" @click="clarify">Request Clarification</button>
    <button class="btn btn-mint" @click="approve">Approve</button>
    <button class="btn btn-rose" @click="reject">Reject</button>
    <button class="btn btn-grey" @click="reject">Reassign Coordinator</button>
  </div>
  <p v-if="actionError" class="field-error">{{ actionError }}</p>
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

      <div v-if="confirmState" class="confirm-overlay">
        <div class="confirm-box">
          <p>{{ confirmState.message }}</p>
          <div class="actions">
            <button class="btn btn-rose" @click="confirmState.onConfirm">Yes, continue</button>
            <button class="btn btn-grey" @click="confirmState.onCancel">Cancel</button>
          </div>
        </div>
      </div>

      <div class="action-block">

        <label>
          Reassign to
          <select v-model.number="newCoordinatorId">
            <option disabled :value="null">Select a coordinator</option>
            <option v-for="c in otherCoordinators" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
        <div class="actions">
          <button class="btn btn-primary" :disabled="!newCoordinatorId" @click="reassign">Reassign (after offline agreement)</button>
        </div>

      </div>
    </section>

    <!-- Organiser Actions: Event Review and Approval -->
    <section v-if="isOwningOrganiser">
      <template v-if="canRespondToClarifications && openClarifications.length">
        <h3 class="section-title">Clarification Requests Awaiting Your Response</h3>
        <div v-for="item in openClarifications" :key="item.reviewId" class="action-block">
          <p class="request-question">{{ item.request.comments }}</p>
          <span class="thread-meta">Asked {{ formatDate(item.request.createdAt) }}</span>

          <label class="field-row">
            Your response
            <div>
              <textarea
              v-model="openResponseForms[item.reviewId].comments"
              placeholder="Explain what you changed, or answer the coordinator's question"
            ></textarea>
            </div>
          </label>

          <template v-if="item.request.editableFields?.length">
            <div
              v-for="field in EDITABLE_FIELD_OPTIONS.filter((o) => item.request.editableFields.includes(o.key))"
              :key="field.key"
              class="field-row"
            >
              <label>
                {{ field.label }}
                <input
                  v-if="field.type === 'checkbox'"
                  type="checkbox"
                  v-model="openResponseForms[item.reviewId].fields[field.key]"
                />
                <textarea
                  v-else-if="field.type === 'textarea'"
                  v-model="openResponseForms[item.reviewId].fields[field.key]"
                ></textarea>
                <input
                  v-else-if="field.type === 'number'"
                  type="number"
                  v-model.number="openResponseForms[item.reviewId].fields[field.key]"
                />
                <input v-else :type="field.type" v-model="openResponseForms[item.reviewId].fields[field.key]" />
              </label>
            </div>
          </template>
          <p v-else class="notice-inline">
            The coordinator hasn't opened any fields for editing on this request. You can still respond in words.
          </p>

          <p v-if="respondErrors[item.reviewId]" class="field-error">{{ respondErrors[item.reviewId] }}</p>
          <div class="actions">
            <button class="btn btn-primary" @click="respondToItem(item.reviewId)">Send Response</button>
          </div>
        </div>
      </template>

      <div v-if="event.status === 'rejected' && event.canResubmit" class="action-block">
        <h3 class="block-title">Revise and Resubmit</h3>
        <p class="notice-inline">Update the details below, then resubmit for review.</p>

        <label class="field-row">
          Event name
          <p></p>
          <input v-model="revisionForm.name" />
        </label>
        <label class="field-row">
          Purpose
          <p></p>
          <input v-model="revisionForm.purpose" />
        </label>
        <label class="field-row">
          Description
          <p></p>
          <textarea v-model="revisionForm.description"></textarea>
        </label>
        <label class="field-row">
          Proposed date
          <p></p>
          <input v-model="revisionForm.proposed_date" type="date" />
        </label>
        <label class="field-row">
          Proposed time
          <p></p>
          <input v-model="revisionForm.proposed_time" type="time" />
        </label>
        <label class="field-row">
          Expected attendance
          <p></p>
          <input v-model.number="revisionForm.expected_attendance" type="number" min="1" />
        </label>
        <label class="field-row">
          Equipment Required
          <p></p>
          <input v-model.number="revisionForm.capacity_needed" type="number" min="1" />
        </label>
        <label class="field-row">
          Venue Required
          <p></p>
          <input v-model="revisionForm.required_layout" />
        </label>
        <label class="field-row">
          Accessibility needs
          <p></p>
          <textarea v-model="revisionForm.accessibility_needs"></textarea>
        </label>
        <label class="checkbox-option">
          <input v-model="revisionForm.registration_required" type="checkbox" />
          Registration required
        </label>

        <p v-if="revisionError" class="field-error">{{ revisionError }}</p>
        <div class="actions">
          <button class="btn btn-primary" @click="resubmit">Resubmit for Review</button>
        </div>
      </div>
      <div v-else-if="event.status === 'rejected' && !event.canResubmit" class="action-block">
        <h3 class="block-title">Revise and Resubmit</h3>
        <p class="notice-inline">
          This request has already been resubmitted. Open the latest resubmission from your Dashboard to see its status.
        </p>
      </div>
    </section>
  </div>
  <p v-else class="loading">Loading…</p>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import eventsApi from "../api/events";
import usersApi from "../api/users";
import { useConfirm } from "../composables/useConfirm";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const event = ref(null);
const comment = ref("");
const responseNotes = ref("");
const newCoordinatorId = ref(null);
const coordinators = ref([]);

const clarificationError = ref("");
const reviewHistory = ref([]);

const confirmState = ref(null); // { message, onConfirm, onCancel }
const actionError = ref("");
const { confirm } = useConfirm();

const EDITABLE_FIELD_OPTIONS = [
  { key: "name", label: "Event name", type: "text" },
  { key: "purpose", label: "Purpose", type: "text" },
  { key: "description", label: "Description", type: "textarea" },
  { key: "proposed_date", label: "Proposed date", type: "date" },
  { key: "proposed_time", label: "Proposed time", type: "time" },
  { key: "expected_attendance", label: "Expected attendance", type: "number" },
  { key: "capacity_needed", label: "Equipment Required", type: "number" },
  { key: "required_layout", label: "Venue Required", type: "text" },
  { key: "accessibility_needs", label: "Accessibility needs", type: "textarea" },
  { key: "registration_required", label: "Registration required", type: "checkbox" },
];

const editableFields = ref([]);       // coordinator's selection when requesting clarification

// "under_review" -> "under review"
const statusLabel = (status) => (status || "").replace(/_/g, " ");

const isAssignedCoordinator = computed(
  () => auth.hasRole("event_coordinator") && event.value?.coordinatorId === auth.user?.id
);
const isOwningOrganiser = computed(
  () => auth.hasRole("event_organiser") && event.value?.organiserId === auth.user?.id
);
// Exclude yourself — reassigning "to" the coordinator who already owns it is a no-op the backend rejects anyway.
const otherCoordinators = computed(() => coordinators.value.filter((c) => c.id !== auth.user?.id));

const clarificationThread = ref([]);
const openResponseForms = reactive({}); // keyed by reviewId -> { comments, fields }
const respondErrors = reactive({});     // keyed by reviewId -> error string

const canRespondToClarifications = computed(
  () => !["approved", "rejected", "cancelled"].includes(event.value?.status)
);

const openClarifications = computed(() =>
  clarificationThread.value.filter((item) => item.response === null && !item.withdrawn)
);

const priorDecisions = ref([]);
const revisionForm = reactive({
  name: "",
  purpose: "",
  description: "",
  proposed_date: "",
  proposed_time: "",
  expected_attendance: null,
  capacity_needed: null,
  required_layout: "",
  accessibility_needs: "",
  registration_required: false,
});
const revisionError = ref("");

const formatFieldNames = (keys) =>
  (keys || []).map((k) => EDITABLE_FIELD_OPTIONS.find((o) => o.key === k)?.label || k).join(", ");

const formatDate = (iso) => (iso ? new Date(iso).toLocaleString() : "");

async function load() {
  const { data } = await eventsApi.getEvent(route.params.id);
  event.value = data;
  initRevisionForm();

  try {
    const { data: outcome } = await eventsApi.getOutcome(route.params.id);
    reviewHistory.value = outcome.reviewHistory || [];
    clarificationThread.value = outcome.clarificationThread || [];
    priorDecisions.value = outcome.priorDecisions || [];
  } catch (e) {
    reviewHistory.value = [];
    clarificationThread.value = [];
    priorDecisions.value = [];
  }

  clarificationThread.value.filter((item) => item.response === null).forEach(ensureResponseForm);
}

async function loadCoordinators() {
  const { data } = await usersApi.listCoordinators();
  coordinators.value = data;
}

async function clarify() {
  clarificationError.value = "";
  try {
    await eventsApi.requestClarification(event.value.id, comment.value, editableFields.value);
    comment.value = "";
    editableFields.value = [];
    await load();
  } catch (e) {
    clarificationError.value = e.response?.data?.error || "Could not request clarification.";
  }
}

function ensureResponseForm(item) {
  if (openResponseForms[item.reviewId]) return;
  const source = {
    name: event.value.name,
    purpose: event.value.purpose,
    description: event.value.description,
    proposed_date: event.value.proposedDate,
    proposed_time: event.value.proposedTime,
    expected_attendance: event.value.expectedAttendance,
    capacity_needed: event.value.venueRequirements?.capacityNeeded,
    required_layout: event.value.venueRequirements?.requiredLayout,
    accessibility_needs: event.value.venueRequirements?.accessibilityNeeds,
    registration_required: event.value.registrationRequired,
  };
  const fields = {};
  (item.request.editableFields || []).forEach((key) => {
    fields[key] = source[key] ?? (key === "registration_required" ? false : "");
  });
  openResponseForms[item.reviewId] = { comments: "", fields };
}

function initRevisionForm() {
  if (event.value?.status !== "rejected") return;
  revisionForm.name = event.value.name || "";
  revisionForm.purpose = event.value.purpose || "";
  revisionForm.description = event.value.description || "";
  revisionForm.proposed_date = event.value.proposedDate || "";
  revisionForm.proposed_time = event.value.proposedTime || "";
  revisionForm.expected_attendance = event.value.expectedAttendance;
  revisionForm.capacity_needed = event.value.venueRequirements?.capacityNeeded;
  revisionForm.required_layout = event.value.venueRequirements?.requiredLayout;
  revisionForm.accessibility_needs = event.value.venueRequirements?.accessibilityNeeds;
  revisionForm.registration_required = event.value.registrationRequired;
}

function requestActionWithConfirmation(callWithConfirmed) {
  return new Promise((resolve, reject) => {
    callWithConfirmed(false)
      .then(({ data }) => resolve(data))
      .catch((e) => {
        if (e.response?.status === 409 && e.response.data?.requiresConfirmation) {
          confirmState.value = {
            message: e.response.data.message,
            onConfirm: () => {
              confirmState.value = null;
              callWithConfirmed(true)
                .then(({ data }) => resolve(data))
                .catch(reject);
            },
            onCancel: () => {
              confirmState.value = null;
              resolve(null);
            },
          };
        } else {
          reject(e);
        }
      });
  });
}

async function respondToItem(reviewId) {
  respondErrors[reviewId] = "";
  const form = openResponseForms[reviewId];
  try {
    await eventsApi.respondClarification(event.value.id, {
      reviewId,
      comments: form.comments,
      ...form.fields,
    });
    delete openResponseForms[reviewId];
    delete respondErrors[reviewId];
    await load();
  } catch (e) {
    respondErrors[reviewId] = e.response?.data?.error || "Could not send response.";
  }
}

async function approve() {
  actionError.value = "";
  try {
    const data = await requestActionWithConfirmation((confirmed) =>
      eventsApi.approveEvent(event.value.id, comment.value, confirmed)
    );
    if (data) {
      comment.value = "";
      await load();
    }
  } catch (e) {
    actionError.value = e.response?.data?.error || "Could not approve this request.";
  }
}

async function reject() {
  actionError.value = "";
  try {
    const data = await requestActionWithConfirmation((confirmed) =>
      eventsApi.rejectEvent(event.value.id, comment.value, confirmed)
    );
    if (data) {
      comment.value = "";
      await load();
    }
  } catch (e) {
    actionError.value = e.response?.data?.error || "Could not reject this request.";
  }
}

async function cancelEvent() {
  actionError.value = "";
  try {
    const data = await requestActionWithConfirmation((confirmed) =>
      eventsApi.cancelEvent(event.value.id, comment.value, confirmed)
    );
    if (data) {
      comment.value = "";
      await load();
    }
  } catch (e) {
    actionError.value = e.response?.data?.error || "Could not cancel this event.";
  }
}

async function deleteClarificationRequest(reviewId) {
  actionError.value = "";

  const confirmed = await confirm(
    "Delete this clarification request? The organiser will no longer be able to respond to it."
  );
  if (!confirmed) return;

  try {
    await eventsApi.deleteClarification(event.value.id, reviewId);
    await load();
  } catch (e) {
    actionError.value = e.response?.data?.error || "Could not delete this clarification request.";
  }
}

async function revertToPlanning() {
  const confirmed = await confirm(
    "Revert this confirmed event back to Planning? This should only be done for a major change."
  );
  if (!confirmed) return;

  await eventsApi.changeStatus(event.value.id, "planning", comment.value);
  comment.value = "";
  await load();
}

async function reassign() {
  if (!newCoordinatorId.value) return;

  const confirmed = await confirm("Reassign this event to the selected coordinator?");
  if (!confirmed) return;

  await eventsApi.reassign(event.value.id, newCoordinatorId.value);
  newCoordinatorId.value = null;
  await load();
}

async function resubmit() {
  revisionError.value = "";

  const confirmed = await confirm("Resubmit this request for review with your changes?");
  if (!confirmed) return;

  try {
    const { data } = await eventsApi.resubmitEvent(event.value.id, { ...revisionForm });
    router.push(`/events/${data.id}`);
  } catch (e) {
    revisionError.value = e.response?.data?.error || "Could not resubmit this request.";
  }
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

.history-list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.history-list li {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.6rem 0.75rem;
  border-radius: 10px;
  background: var(--sky-bg, #d6ecff);
}

.history-date {
  font-size: 0.75rem;
  color: var(--sky-text, #1f5f99);
}

.history-comment {
  color: var(--text, #2d2a4a);
}

.field-error {
  margin: 0;
  color: var(--rose-text, #a12b47);
  font-size: 0.85rem;
}

.field-select {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.4rem 1rem;
}

.checkbox-option {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 400;
}

.field-row label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text, #2d2a4a);
}

.editable-fields-note {
  margin-top: 0.35rem;
  font-size: 0.85rem;
  font-weight: 500;
}

.notice-inline {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-muted, #6b6890);
}

.thread-list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.thread-item {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding-bottom: 0.6rem;
  border-bottom: 1px solid var(--border, #e4defa);
}

.thread-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.thread-message {
  padding: 0.6rem 0.75rem;
  border-radius: 10px;
}

.thread-message.request {
  background: var(--butter-bg, #fff1c2);
}

.thread-message.response {
  background: var(--sky-bg, #d6ecff);
  margin-left: 1rem;
}

.thread-message p {
  margin: 0.2rem 0 0;
  color: var(--text, #2d2a4a);
}

.thread-meta {
  font-size: 0.75rem;
  font-weight: 600;
  opacity: 0.75;
}

.thread-fields {
  font-size: 0.8rem;
  font-style: italic;
}

.thread-pending {
  margin-left: 1rem;
  font-size: 0.85rem;
  color: var(--text-muted, #6b6890);
}

.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.confirm-box {
  background: #fff;
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.thread-withdrawn {
  margin-left: 1rem;
  font-size: 0.85rem;
  font-style: italic;
  color: var(--text-muted, #6b6890);
}

.thread-pending {
  margin-left: 1rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.85rem;
  color: var(--text-muted, #6b6890);
}

.btn-small {
  padding: 0.2rem 0.6rem;
  font-size: 0.8rem;
}

.notice.approved {
  background: var(--mint-bg, #d3f5e3);
  color: var(--mint-text, #1e6b47);
}

.notice.rejected {
  background: var(--rose-bg, #fbdcdc);
  color: var(--rose-text, #a12b47);
}

.decision-meta {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  font-weight: 400;
  opacity: 0.85;
}

.decision-reason {
  margin: 0.35rem 0 0;
  font-weight: 400;
}

.thread-message.approved {
  background: var(--mint-bg, #d3f5e3);
}

.thread-message.rejected {
  background: var(--rose-bg, #fbdcdc);
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

.reg-pill {
  display: inline-block;
  padding: 0.1rem 0.6rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  background: #e2e5ea;
  color: #55585e;
  width: fit-content;
}

.reg-pill.required {
  background: var(--mint-bg, #d3f5e3);
  color: var(--mint-text, #1e6b47);
}

.accessibility {
  margin-top: 0.85rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--border, #e4defa);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.accessibility p {
  margin: 0;
  color: var(--text, #2d2a4a);
  line-height: 1.5;
}

.request-question {
  margin: 0;
  font-weight: 600;
  color: var(--text, #2d2a4a);
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

.btn-grey {
  background: #c6cfd7;
  color: #626364;
}
.btn-grey:hover {
  background: #b0b3b6;
}
</style>