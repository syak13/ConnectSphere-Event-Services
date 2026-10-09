<template>
  <div>
    <h2 class="page-title">Venue Booking</h2>

    <div class="tabs" role="tablist" aria-label="Venue booking sections">
      <button type="button" role="tab" :aria-selected="activeTab === 'submit'"
        :class="['tab', { active: activeTab === 'submit' }]"
        @click="activeTab = 'submit'">Submit Booking Request</button>
      <button type="button" role="tab" :aria-selected="activeTab === 'status'"
        :class="['tab', { active: activeTab === 'status' }]"
        @click="switchTab('status')">My Booking Requests</button>
    </div>

    <div v-show="activeTab === 'submit'">
      <div class="card">
        <form @submit.prevent="submitBooking">
          <div class="section">
            <h3>Event</h3>
            <div class="form-group">
              <label for="event">Select Event *</label>
              <select id="event" v-model="eventId" required>
                <option value="" disabled>Select an event</option>
                <option v-for="event in events" :key="event.id" :value="event.id">
                  {{ event.name || event.title || `Event ${event.id}` }}
                </option>
              </select>
            </div>

            <div v-if="selectedEvent" class="requirements-box">
              <h4>Event Venue Requirements</h4>
              <div class="requirements-grid">
                <div>
                  <span class="requirement-label">Capacity Needed</span>
                  <span>{{ selectedEvent.venueRequirements?.capacityNeeded ?? "Not specified" }}</span>
                </div>
                <div>
                  <span class="requirement-label">Required Layout</span>
                  <span>{{ selectedEvent.venueRequirements?.requiredLayout || "Not specified" }}</span>
                </div>
                <div>
                  <span class="requirement-label">Accessibility Needs</span>
                  <span>{{ selectedEvent.venueRequirements?.accessibilityNeeds || "Not specified" }}</span>
                </div>
                <div>
                  <span class="requirement-label">Required Facilities</span>
                  <span>{{ formatFacilities(selectedEvent.venueRequirements?.requiredFacilities) }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-heading">
              <div>
                <h3>Venues</h3>
                <p class="section-description">
                  Add one or more venues for this event. Each venue can have its own booking timing.
                </p>
              </div>
              <button type="button" class="btn secondary" @click="addVenue">+ Add Venue</button>
            </div>

            <div v-for="(venueRequest, index) in venueRequests" :key="venueRequest.key" class="venue-card">
              <div class="venue-heading">
                <h4>Venue {{ index + 1 }}</h4>
                <button v-if="venueRequests.length > 1" type="button" class="remove-btn"
                  @click="removeVenue(index)">Remove</button>
              </div>
              <div class="form-group">
                <label :for="`venue-${index}`">Venue *</label>
                <select :id="`venue-${index}`" v-model="venueRequest.venueId" required>
                  <option value="" disabled>Select a venue</option>
                  <option v-for="venue in availableVenues(index)" :key="venue.id" :value="venue.id">
                    {{ venue.name }}
                  </option>
                </select>
                <p v-if="fieldError(index, 'venue_id')" class="field-error">
                  {{ fieldError(index, "venue_id") }}
                </p>
              </div>

              <h5 class="subheading">Timing</h5>
              <div class="form-grid">
                <div class="form-group">
                  <label :for="`date-${index}`">Date *</label>
                  <input :id="`date-${index}`" v-model="venueRequest.date" type="date" :min="today" required />
                  <p v-if="fieldError(index, 'date')" class="field-error">{{ fieldError(index, "date") }}</p>
                </div>
                <div class="form-group">
                  <label :for="`start-${index}`">Start Time *</label>
                  <input :id="`start-${index}`" v-model="venueRequest.startTime" type="time" required />
                  <p v-if="fieldError(index, 'start_time')" class="field-error">
                    {{ fieldError(index, "start_time") }}
                  </p>
                </div>
                <div class="form-group">
                  <label :for="`end-date-${index}`">End Date</label>
                  <input :id="`end-date-${index}`" v-model="venueRequest.endDate"
                    type="date" :min="venueRequest.date || today" />
                  <p class="hint">Only needed if the booking ends on another day.</p>
                  <p v-if="fieldError(index, 'end_date')" class="field-error">
                    {{ fieldError(index, "end_date") }}
                  </p>
                </div>
                <div class="form-group">
                  <label :for="`end-${index}`">End Time *</label>
                  <input :id="`end-${index}`" v-model="venueRequest.endTime" type="time" required />
                  <p v-if="fieldError(index, 'end_time')" class="field-error">
                    {{ fieldError(index, "end_time") }}
                  </p>
                </div>
              </div>
            </div>

            <div v-if="generalErrors.length" class="error-message">
              <p v-for="(error, index) in generalErrors" :key="index">{{ error }}</p>
            </div>
          </div>

          <div class="actions">
            <button type="button" class="btn secondary" @click="resetForm">Clear</button>
            <button type="submit" class="btn" :disabled="submitting">
              {{ submitting ? "Submitting..." : "Submit Booking Request" }}
            </button>
          </div>
        </form>
      </div>
      <div v-if="successMessage" class="success-message">{{ successMessage }}</div>
    </div>

    <section v-if="activeTab === 'status'" class="card status-section">
      <div class="section-heading">
        <div>
          <h3>My Booking Requests</h3>
          <p class="section-description">Each venue has its own booking status.</p>
        </div>
        <button type="button" class="btn secondary" @click="loadMyBookings" :disabled="statusLoading">
          {{ statusLoading ? "Refreshing..." : "Refresh Status" }}
        </button>
      </div>

      <p v-if="statusError" class="error-message" role="alert">{{ statusError }}</p>
      <p v-if="statusLoading" class="status-message">Loading booking requests...</p>
      <p v-else-if="!statusError && myBookings.length === 0" class="status-message">
        You haven't submitted any venue booking requests yet.
      </p>

      <div v-if="myBookings.length" class="booking-list">
        <article v-for="booking in myBookings" :key="booking.id" class="booking-card">
          <div class="booking-heading">
            <div>
              <h4>{{ booking.eventName || `Event #${booking.eventId}` }}</h4>
              <p class="venue-label">{{ booking.venueName || `Venue #${booking.venueId}` }}</p>
            </div>
            <span class="status-pill" :class="booking.status">
              {{ formatStatus(booking.status) }}
            </span>
          </div>
          <div class="booking-details">
            <p><strong>Booking ID:</strong> #{{ booking.id }}</p>
            <p><strong>Start:</strong> {{ formatBookingDate(booking.startDatetime) }}</p>
            <p><strong>End:</strong> {{ formatBookingDate(booking.endDatetime) }}</p>
            <p><strong>Submitted:</strong> {{ formatBookingDate(booking.createdAt) }}</p>
          </div>
          <p v-if="booking.status === 'rejected' && booking.decisionReason" class="rejection-reason">
            <strong>Reason for rejection:</strong> {{ booking.decisionReason }}
          </p>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import eventsApi from "../api/events";
import venuesApi from "../api/venues";

const activeTab = ref("submit");
const events = ref([]);
const venues = ref([]);
const eventId = ref("");
const submitting = ref(false);
const errors = ref([]);
const successMessage = ref("");

const myBookings = ref([]);
const statusLoading = ref(false);
const statusError = ref("");

const selectedEvent = computed(() =>
  events.value.find((event) => Number(event.id) === Number(eventId.value))
);

const today = new Date().toLocaleDateString("en-CA");
let nextVenueKey = 0;
const emptyVenue = () => ({
  key: nextVenueKey++,
  venueId: "",
  date: "",
  startTime: "",
  endTime: "",
  endDate: "",
});
const venueRequests = ref([emptyVenue()]);

function formatFacilities(value) {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "Not specified";
  return value || "Not specified";
}

function availableVenues(currentIndex) {
  const selectedIds = venueRequests.value
    .filter((_, index) => index !== currentIndex)
    .map((request) => Number(request.venueId))
    .filter(Boolean);
  return venues.value.filter((venue) => !selectedIds.includes(Number(venue.id)));
}

function addVenue() {
  venueRequests.value.push(emptyVenue());
}

function removeVenue(index) {
  venueRequests.value.splice(index, 1);
  errors.value = [];
}

function resetForm() {
  eventId.value = "";
  venueRequests.value = [emptyVenue()];
  errors.value = [];
  successMessage.value = "";
}

function fieldError(index, field) {
  const request = venueRequests.value[index];
  const matchingError = errors.value.find((error) => {
    if (error.field !== field) return false;
    if (error.venue_id != null) {
      return Number(error.venue_id) === Number(request.venueId);
    }
    return error.venue === `Venue ${index + 1}`;
  });
  return matchingError?.message || "";
}

const generalErrors = computed(() =>
  errors.value.filter((error) => error.field === "venues").map((error) => error.message)
);

async function submitBooking() {
  errors.value = [];
  successMessage.value = "";

  if (!eventId.value) {
    errors.value = [{ field: "venues", message: "Please select an event." }];
    return;
  }

  submitting.value = true;
  try {
    const payload = {
      eventId: Number(eventId.value),
      venues: venueRequests.value.map((venue) => ({
        venueId: Number(venue.venueId),
        date: venue.date,
        startTime: venue.startTime,
        endTime: venue.endTime,
        endDate: venue.endDate || null,
      })),
    };

    await venuesApi.submitBooking(payload);
    successMessage.value = "Venue booking request submitted successfully.";
    venueRequests.value = [emptyVenue()];
  } catch (error) {
    const data = error.response?.data;
    if (Array.isArray(data?.errors)) {
      errors.value = data.errors;
    } else {
      errors.value = [{
        field: "venues",
        message: data?.error || "Unable to submit the booking request.",
      }];
    }
  } finally {
    submitting.value = false;
  }
}

async function loadMyBookings() {
  statusLoading.value = true;
  statusError.value = "";

  try {
    const response = await venuesApi.getMyBookings();
    myBookings.value = response.data;
  } catch (error) {
    myBookings.value = []; // Clear outdated booking statuses

    statusError.value =
      error.response?.data?.error ||
      "Unable to load your booking requests.";
  } finally {
    statusLoading.value = false;
  }
}

async function switchTab(tab) {
  activeTab.value = tab;
  if (tab === "status") await loadMyBookings();
}

function formatStatus(status) {
  const labels = {
    pending: "Pending",
    approved: "Approved",
    rejected: "Rejected",
    withdrawn: "Withdrawn",
  };
  return labels[status] || status || "Unknown";
}

function formatBookingDate(value) {
  if (!value) return "N/A";
  // Database DATETIME values are timezone-naive; don't shift their clock times.
  const [date, time = ""] = String(value).replace(" ", "T").split("T");
  return `${date} ${time.slice(0, 5)}`.trim();
}

onMounted(async () => {
  try {
    const eventsResponse = await eventsApi.assignedEvents();
    events.value = eventsResponse.data;
  } catch (error) {
    console.error("EVENTS ERROR:", error);
  }

  try {
    const venuesResponse = await venuesApi.listVenues();
    venues.value = venuesResponse.data;
  } catch (error) {
    console.error("VENUES ERROR:", error);
  }
});
</script>

<style scoped>
.page-title { margin: 0 0 1rem; font-size: 1.5rem; font-weight: 600; color: var(--text, #2d2a4a); }
.card { background: var(--surface, #fff); border: 1px solid var(--border, #e4defa); border-radius: 14px; box-shadow: 0 4px 16px rgba(109, 91, 208, .08); overflow: hidden; }
.section { padding: 1.25rem; border-bottom: 1px solid var(--border, #e4defa); }
.section:last-child { border-bottom: none; }
.section h3, .status-section h3 { margin: 0 0 1rem; color: var(--text, #2d2a4a); font-size: 1.1rem; font-weight: 600; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.section-heading h3 { margin-bottom: .25rem; }
.section-description { margin: 0; color: var(--text-muted, #6b6890); font-size: .9rem; }
.venue-card { margin-top: 1rem; padding: 1.25rem; background: #faf9ff; border: 1px solid var(--border, #e4defa); border-radius: 12px; }
.venue-heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.venue-heading h4 { margin: 0; color: var(--lilac-text, #4b3fa0); font-size: 1rem; }
.subheading { margin: 1rem 0 .8rem; color: var(--text, #2d2a4a); font-size: .95rem; font-weight: 600; }
.form-group { display: flex; flex-direction: column; gap: .35rem; margin-bottom: 1rem; }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 1rem; }
label { color: var(--text, #2d2a4a); font-size: .875rem; font-weight: 500; }
input, select, textarea { width: 100%; box-sizing: border-box; padding: .65rem .75rem; border: 1px solid var(--border, #e4defa); border-radius: 8px; background: #fff; color: var(--text, #2d2a4a); font: inherit; }
input:focus, select:focus, textarea:focus { outline: 2px solid var(--primary, #6d5bd0); outline-offset: 1px; border-color: var(--primary, #6d5bd0); }
.hint { margin: 0; color: var(--text-muted, #6b6890); font-size: .78rem; }
.field-error { margin: .25rem 0 0; color: var(--rose-text, #a12b47); font-size: .85rem; }
.error-message { margin-top: 1rem; padding: .8rem 1rem; background: var(--rose-bg, #fde8ee); color: var(--rose-text, #a12b47); border-radius: 8px; font-size: .875rem; }
.error-message p { margin: .2rem 0; }
.success-message { margin-top: 1rem; padding: .9rem 1rem; border-radius: 10px; background: var(--mint-bg, #d3f5e3); color: var(--mint-text, #1e6b47); font-weight: 500; }
.actions { display: flex; justify-content: flex-end; gap: .75rem; padding: 1.25rem; }
.btn { display: inline-block; padding: .55rem 1.1rem; border: none; border-radius: 999px; background: var(--primary, #6d5bd0); color: #fff; font: inherit; font-weight: 500; cursor: pointer; }
.btn:hover:not(:disabled) { background: var(--primary-hover, #5b49bd); }
.btn.secondary { background: var(--lilac-bg, #e9e5fb); color: var(--lilac-text, #4b3fa0); }
.btn.secondary:hover { background: #ddd6fb; }
.btn:disabled { opacity: .6; cursor: not-allowed; }
.remove-btn { border: none; background: transparent; color: var(--rose-text, #a12b47); font: inherit; font-size: .85rem; font-weight: 500; cursor: pointer; }
.remove-btn:hover { text-decoration: underline; }
.requirements-box { margin-top: 1rem; padding: 1rem; background: #faf9ff; border: 1px solid var(--border, #e4defa); border-radius: 10px; }
.requirements-box h4 { margin: 0 0 .8rem; color: var(--lilac-text, #4b3fa0); font-size: .95rem; }
.requirements-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: .8rem 1.5rem; }
.requirements-grid > div { display: flex; flex-direction: column; gap: .2rem; }
.requirement-label { color: var(--text-muted, #6b6890); font-size: .78rem; font-weight: 500; }
.tabs { display: flex; gap: .5rem; margin: 0 0 1.25rem; border-bottom: 1px solid var(--border, #e4defa); }
.tab { padding: .8rem 1rem; border: none; border-bottom: 3px solid transparent; background: transparent; color: var(--text-muted, #6b6890); font: inherit; font-weight: 600; cursor: pointer; }
.tab.active { color: var(--lilac-text, #4b3fa0); border-bottom-color: var(--primary, #6d5bd0); }
.status-section { padding: 1.25rem; }
.status-message { color: var(--text-muted, #6b6890); }
.booking-list { display: grid; gap: 1rem; }
.booking-card { padding: 1.25rem; background: #faf9ff; border: 1px solid var(--border, #e4defa); border-radius: 12px; }
.booking-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.booking-heading h4 { margin: 0 0 .35rem; color: var(--text, #2d2a4a); }
.venue-label { margin: 0; color: var(--text-muted, #6b6890); }
.booking-details { margin-top: 1rem; display: grid; grid-template-columns: repeat(2, 1fr); gap: .6rem 1rem; }
.booking-details p { margin: 0; font-size: .875rem; }
.status-pill { display: inline-block; border-radius: 999px; padding: .4rem .75rem; font-size: .8rem; font-weight: 600; white-space: nowrap; }
.status-pill.pending { background: #fef3c7; color: #92400e; }
.status-pill.approved { background: #d3f5e3; color: #1e6b47; }
.status-pill.rejected { background: #fde8ee; color: #a12b47; }
.status-pill.withdrawn { background: #e9e5fb; color: #4b3fa0; }
.rejection-reason { margin: 1rem 0 0; padding: .75rem; border-radius: 8px; background: #fde8ee; color: #a12b47; font-size: .875rem; }
@media (max-width: 700px) {
  .form-grid, .requirements-grid, .booking-details { grid-template-columns: 1fr; }
  .section-heading { flex-direction: column; }
  .actions { flex-direction: column-reverse; }
  .actions .btn { width: 100%; }
  .tabs { flex-wrap: wrap; }
  .booking-heading { flex-direction: column; }
}
</style>
