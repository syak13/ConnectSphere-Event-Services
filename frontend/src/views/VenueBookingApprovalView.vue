
<template>
  <section>
    <div class="head">
      <h2 class="page-title">Venue Booking Approval</h2>
      <button
        type="button"
        class="btn-primary"
        :disabled="loading"
        @click="loadPendingBookings"
      >
        {{ loading ? "Refreshing..." : "Refresh requests" }}
      </button>
    </div>

    <p class="intro">
      Pending requests for venues you manage, sorted by the soonest event date.
    </p>

    <p v-if="error" class="field-error" role="alert">
      {{ error }}
    </p>

    <p v-if="notice" class="success" role="status">
      {{ notice }}
    </p>

    <p v-if="loading" class="empty" role="status">
      Loading booking requests...
    </p>

    <p v-else-if="!error && !bookings.length" class="empty">
      No pending booking requests for your venues.
    </p>

    <template v-else-if="!error && !loading">
      <div class="card summary">
        <span class="summary-label">Pending booking requests</span>
        <span class="badge cap">
          {{ bookings.length }}
          {{ bookings.length === 1 ? "request" : "requests" }}
        </span>
      </div>

      <div class="grid" aria-live="polite">
        <article
          v-for="booking in bookings"
          :key="booking.id"
          class="card booking"
        >
          <header>
            <h3>
              {{ booking.eventName || `Event #${booking.eventId}` }}
            </h3>
            <span class="badge cap">Pending</span>
          </header>

          <p class="meta">Request #{{ booking.id }}</p>

          <p class="meta">
            <strong>Venue:</strong>
            {{ booking.venueName || `Venue #${booking.venueId}` }}
          </p>

          <p class="meta">
            <strong>Location:</strong>
            {{ booking.venueLocation || "Not specified" }}
          </p>

          <p class="meta">
            <strong>Event date:</strong>
            {{ formatDate(booking.startDatetime) }}
          </p>

          <p class="meta">
            <strong>Time:</strong>
            {{ formatTime(booking.startDatetime) }}
            –
            {{ formatTime(booking.endDatetime) }}
          </p>

          <div class="chips">
            <span class="badge sky">
              {{ booking.expectedAttendance ?? "Unknown" }} attendees
            </span>
            <span class="badge lilac">
              Submitted {{ formatDate(booking.createdAt) }}
            </span>
          </div>

          <p v-if="booking.eventDescription" class="desc">
            {{ booking.eventDescription }}
          </p>

          <button
            type="button"
            class="btn-primary approve-btn"
            :disabled="approvingId !== null"
            @click="openApprovalConfirmation(booking)"
          >
            {{ approvingId === booking.id ? "Approving..." : "Approve booking" }}
          </button>
        </article>
      </div>
    </template>

    <!-- Approval confirmation pop-up -->
    <div
      v-if="bookingToApprove"
      class="modal-backdrop"
      @click.self="cancelApproval"
    >
      <div
        class="confirmation-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="approve-dialog-title"
        aria-describedby="approve-dialog-description"
      >
        <h3 id="approve-dialog-title">
          Approve booking request?
        </h3>

        <p id="approve-dialog-description">
          Are you sure you want to approve the booking for
          <strong>
            {{ bookingToApprove.eventName || `Event #${bookingToApprove.eventId}` }}
          </strong>
          at
          <strong>
            {{ bookingToApprove.venueName || `Venue #${bookingToApprove.venueId}` }}
          </strong>?

          This will confirm the venue for the event.
        </p>

        <p class="dialog-time">
          <strong>Start:</strong>
          {{ formatDate(bookingToApprove.startDatetime) }}
          {{ formatTime(bookingToApprove.startDatetime) }}

          <br />

          <strong>End:</strong>
          {{ formatDate(bookingToApprove.endDatetime) }}
          {{ formatTime(bookingToApprove.endDatetime) }}
        </p>

        <div class="confirmation-actions">
          <button
            type="button"
            class="btn-primary secondary"
            :disabled="approvingId !== null"
            @click="cancelApproval"
          >
            Cancel
          </button>

          <button
            type="button"
            class="btn-primary"
            :disabled="approvingId !== null"
            @click="confirmApproval"
          >
            {{ approvingId !== null ? "Approving..." : "Yes, Approve" }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import venuesApi from "../api/venues";

const bookings = ref([]);
const loading = ref(false);
const error = ref("");
const notice = ref("");
const approvingId = ref(null);
const bookingToApprove = ref(null);

function formatDate(value) {
  if (!value) return "Not specified";

  const [year, month, day] = String(value)
    .slice(0, 10)
    .split("-");

  return year && month && day
    ? `${day}/${month}/${year}`
    : "Not specified";
}

function formatTime(value) {
  if (!value) return "Not specified";

  return (
    String(value)
      .replace(" ", "T")
      .split("T")[1]
      ?.slice(0, 5) || "Not specified"
  );
}

async function loadPendingBookings() {
  loading.value = true;
  error.value = "";
  bookings.value = [];

  try {
    const { data } = await venuesApi.getPendingBookings();

    if (!Array.isArray(data)) {
      throw new Error("Unexpected response format");
    }

    bookings.value = data
      .filter((booking) => booking.status === "pending")
      .sort((a, b) =>
        String(a.startDatetime || "").localeCompare(
          String(b.startDatetime || "")
        )
      );
  } catch (err) {
    error.value =
      err.response?.data?.error ||
      "Could not load pending booking requests.";
  } finally {
    loading.value = false;
  }
}

function openApprovalConfirmation(booking) {
  if (
    approvingId.value !== null ||
    booking.status !== "pending"
  ) {
    return;
  }

  bookingToApprove.value = booking;
  error.value = "";
}

function cancelApproval() {
  if (approvingId.value !== null) return;

  bookingToApprove.value = null;
}

async function confirmApproval() {
  const booking = bookingToApprove.value;

  if (!booking || approvingId.value !== null) return;

  approvingId.value = booking.id;
  error.value = "";
  notice.value = "";

  try {
    await venuesApi.approveBooking(booking.id);

    bookingToApprove.value = null;

    await loadPendingBookings();

    notice.value =
      "Booking approved successfully. The venue is confirmed for the event.";
  } catch (err) {
    bookingToApprove.value = null;

    const message =
      err.response?.data?.error ||
      "Unable to approve this booking.";

    if (err.response?.status === 409) {
      await loadPendingBookings();
    }

    error.value = message;
  } finally {
    approvingId.value = null;
  }
}

onMounted(loadPendingBookings);
</script>

<style scoped>
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text, #2d2a4a);
}

.intro {
  margin: 0 0 1rem;
  color: var(--text-muted, #6b6890);
}

.card {
  padding: 1.25rem 1.5rem;
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e4defa);
  border-radius: 14px;
  box-shadow: 0 4px 16px rgba(109, 91, 208, 0.08);
}

.summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.summary-label {
  font-weight: 600;
  color: var(--text, #2d2a4a);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 1rem;
}

.booking header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}

.booking h3 {
  margin: 0 0 0.4rem;
  font-size: 1.1rem;
  color: var(--text, #2d2a4a);
}

.meta {
  margin: 0.2rem 0;
  color: var(--text-muted, #6b6890);
  font-size: 0.92rem;
}

.meta strong {
  color: var(--text, #2d2a4a);
  font-weight: 600;
}

.desc {
  color: var(--text, #2d2a4a);
  margin: 0.75rem 0 0;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border, #e4defa);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.7rem;
}

.badge {
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 500;
  white-space: nowrap;
}

.cap {
  background: var(--butter-bg, #fef3c7);
  color: var(--butter-text, #92400e);
}

.sky {
  background: var(--sky-bg, #e3f2ff);
  color: var(--sky-text, #356b99);
}

.lilac {
  background: var(--lilac-bg, #e9e5fb);
  color: var(--lilac-text, #4b3fa0);
}

.btn-primary {
  padding: 0.5rem 1.2rem;
  border: none;
  border-radius: 999px;
  font: inherit;
  font-weight: 500;
  background: var(--primary, #6d5bd0);
  color: #fff;
  cursor: pointer;
}

.btn-primary:hover {
  background: var(--primary-hover, #5b49bd);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary:focus-visible {
  outline: 2px solid var(--primary, #6d5bd0);
  outline-offset: 2px;
}

.approve-btn {
  margin-top: 1rem;
}

.success {
  color: #166534;
  background: #dcfce7;
  padding: 0.7rem 1rem;
  border-radius: 10px;
}

.field-error {
  color: #a12b47;
  font-size: 0.875rem;
}

.empty {
  padding: 1rem;
  color: var(--text-muted, #6b6890);
}

/* Confirmation modal - same style as Withdraw Booking */
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(28, 22, 54, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.confirmation-dialog {
  width: min(100%, 430px);
  padding: 1.5rem;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 16px 45px rgba(0, 0, 0, 0.2);
}

.confirmation-dialog h3 {
  margin: 0 0 0.75rem;
  color: var(--text, #2d2a4a);
}

.confirmation-dialog p {
  line-height: 1.5;
  color: var(--text, #2d2a4a);
}

.dialog-time {
  padding: 0.75rem;
  border-radius: 8px;
  background: #faf9ff;
}

.confirmation-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.25rem;
}

.btn-primary.secondary {
  background: var(--lilac-bg, #e9e5fb);
  color: var(--lilac-text, #4b3fa0);
}

.btn-primary.secondary:hover {
  background: #ddd6fb;
}

@media (max-width: 560px) {
  .head {
    flex-wrap: wrap;
  }

  .summary {
    flex-wrap: wrap;
  }
}
</style>
