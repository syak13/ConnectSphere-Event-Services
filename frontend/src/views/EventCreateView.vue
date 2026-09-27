<template>
  <div>
    <h2>{{ isEditMode ? "Edit Draft Event Request" : "New Event Request" }}</h2>
    <form @submit.prevent="submit">
      <label>
        Name
        <input v-model="form.name" required />
      </label>
      <label>
        Purpose
        <input v-model="form.purpose" required />
      </label>
      <label>
        Description
        <textarea v-model="form.description" required></textarea>
      </label>
      <label>
        Proposed Date
        <input v-model="form.proposed_date" type="date" :min="todayString" />
      </label>
      <label>
        Proposed Time
        <input v-model="form.proposed_time" type="time" />
      </label>
      <label>
        Expected Attendance
        <input v-model.number="form.expected_attendance" type="number" min="1" />
      </label>
      <label>
        Capacity Needed
        <input v-model.number="form.capacity_needed" type="number" min="1" />
      </label>
      <label>
        Required Layout
        <input v-model="form.required_layout" placeholder="e.g. theatre, banquet" />
      </label>
      <label>
        Accessibility Needs
        <textarea v-model="form.accessibility_needs"></textarea>
      </label>
      <label class="checkbox">
        <input v-model="form.registration_required" type="checkbox" />
        Registration required
      </label>

      <label v-if="form.registration_required">
        Intended Capacity (optional)
        <input
          v-model.number="form.intended_capacity"
          type="number"
          min="1"
          placeholder="Optional if not yet known"
        />
      </label>

      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions">
        <button type="button" @click="saveDraft">
          {{ isEditMode ? "Save Changes" : "Save as Draft" }}
        </button>
        <button type="submit">Submit Now</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import eventsApi from "../api/events";

const route = useRoute();
const router = useRouter();
const error = ref("");
const todayString = new Date().toISOString().split("T")[0];

const draftId = route.params.id;
const isEditMode = Boolean(draftId);
const form = reactive({
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
  intended_capacity: null,
});

async function loadDraft() {
  error.value = "";

  try {
    const { data } = await eventsApi.getEvent(draftId);

    if (data.status !== "draft") {
      error.value = "Only draft event requests can be edited.";
      return;
    }

    Object.assign(form, {
      name: data.name || "",
      purpose: data.purpose || "",
      description: data.description || "",
      proposed_date: data.proposedDate || "",
      proposed_time: data.proposedTime ? data.proposedTime.slice(0, 5) : "",
      expected_attendance: data.expectedAttendance ?? null,
      capacity_needed: data.venueRequirements?.capacityNeeded ?? null,
      required_layout: data.venueRequirements?.requiredLayout || "",
      accessibility_needs:
        data.venueRequirements?.accessibilityNeeds || "",
      registration_required: data.registrationRequired ?? false,
      intended_capacity: data.intendedCapacity ?? null,
    });
  } catch (e) {
    error.value = e.response?.data?.error || "Could not load this draft.";
  }
}

function sanitizePayload(data) {
  const cleaned = { ...data };
  if (cleaned.proposed_date === "") cleaned.proposed_date = null;
  if (cleaned.proposed_time === "") cleaned.proposed_time = null;
  if (cleaned.intended_capacity === "") cleaned.intended_capacity = null;
  return cleaned;
}

function validateDate() {
  if (!form.proposed_date) return true;

  if (form.proposed_date < todayString) {
    error.value = "Proposed date cannot be in the past.";
    return false;
  }

  return true;
}

async function saveDraft() {
  error.value = "";

  if (!validateDate()) {
    return;
  }

  try {
    const payload = sanitizePayload(form);

    if (isEditMode) {
      await eventsApi.updateDraft(draftId, payload);
    } else {
      await eventsApi.saveDraft(payload);
    }

    router.push({ name: "drafts" });
  } catch (e) {
    error.value = e.response?.data?.error || "Could not save draft.";
  }
}

async function submit() {
  error.value = "";

  if (!validateDate()) {
    return;
  }

  try {
    const payload = sanitizePayload(form);

    if (isEditMode) {
      await eventsApi.updateDraft(draftId, payload);
      await eventsApi.submitEvent(draftId);
    } else {
      await eventsApi.createEvent({ ...payload, submit: true });
    }

    router.push({ name: "dashboard" });
  } catch (e) {
    error.value = e.response?.data?.error || "Could not submit request";
  }
}

onMounted(() => {
  if (isEditMode) {
    loadDraft();
  }
});
</script>

<style scoped>
form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-width: 480px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}
label.checkbox {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
input, textarea {
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
.error {
  color: #b00020;
}
</style>
