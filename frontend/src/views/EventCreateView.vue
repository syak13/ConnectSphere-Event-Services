<template>
  <div>
    <h2>New Event Request</h2>
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
        <input v-model="form.proposed_date" type="date" />
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

      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions">
        <button type="button" @click="saveDraft">Save as Draft</button>
        <button type="submit">Submit Now</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import eventsApi from "../api/events";

const router = useRouter();
const error = ref("");
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
});

async function saveDraft() {
  error.value = "";
  try {
    await eventsApi.saveDraft(form);
    router.push({ name: "drafts" });
  } catch (e) {
    error.value = e.response?.data?.error || "Could not save draft";
  }
}

async function submit() {
  error.value = "";
  try {
    await eventsApi.createEvent({ ...form, submit: true });
    router.push({ name: "dashboard" });
  } catch (e) {
    error.value = e.response?.data?.error || "Could not submit request";
  }
}
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
