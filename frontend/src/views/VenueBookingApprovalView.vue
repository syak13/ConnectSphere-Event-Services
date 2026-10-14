<template>
  <section>
    <div class="head">
      <h2 class="page-title">Venue Booking Approval</h2>
      <button type="button" class="btn-primary" :disabled="loading" @click="loadPendingBookings">
        {{ loading ? "Refreshing..." : "Refresh requests" }}
      </button>
    </div>

    <p class="intro">Pending requests for venues you manage, sorted by the soonest event date.</p>
    <p v-if="error" class="field-error" role="alert">{{ error }}</p>
    <p v-if="loading" class="empty" role="status">Loading booking requests...</p>
    <p v-else-if="!error && !bookings.length" class="empty">
      No pending booking requests for your venues.
    </p>

    <template v-else-if="!error && !loading">
      <div class="card summary">
        <span class="summary-label">Pending booking requests</span>
        <span class="badge cap">{{ bookings.length }} {{ bookings.length === 1 ? "request" : "requests" }}</span>
      </div>

      <div class="grid" aria-live="polite">
        <article v-for="booking in bookings" :key="booking.id" class="card booking">
          <header>
            <h3>{{ booking.eventName || `Event #${booking.eventId}` }}</h3>
            <span class="badge cap">Pending</span>
          </header>

          <p class="meta">Request #{{ booking.id }}</p>
          <p class="meta"><strong>Venue:</strong> {{ booking.venueName || `Venue #${booking.venueId}` }}</p>
          <p class="meta"><strong>Location:</strong> {{ booking.venueLocation || "Not specified" }}</p>
          <p class="meta"><strong>Event date:</strong> {{ formatDate(booking.startDatetime) }}</p>
          <p class="meta"><strong>Time:</strong> {{ formatTime(booking.startDatetime) }} – {{ formatTime(booking.endDatetime) }}</p>

          <div class="chips">
            <span class="badge sky">{{ booking.expectedAttendance ?? "Unknown" }} attendees</span>
            <span class="badge lilac">Submitted {{ formatDate(booking.createdAt) }}</span>
          </div>

          <p v-if="booking.eventDescription" class="desc">{{ booking.eventDescription }}</p>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import venuesApi from "../api/venues";

const bookings = ref([]);
const loading = ref(false);
const error = ref("");

function formatDate(value) {
  if (!value) return "Not specified";
  const [year, month, day] = String(value).slice(0, 10).split("-");
  return year && month && day ? `${day}/${month}/${year}` : "Not specified";
}

function formatTime(value) {
  if (!value) return "Not specified";
  return String(value).replace(" ", "T").split("T")[1]?.slice(0, 5) || "Not specified";
}

async function loadPendingBookings() {
  loading.value = true;
  error.value = "";
  bookings.value = [];
  try {
    const { data } = await venuesApi.getPendingBookings();
    if (!Array.isArray(data)) throw new Error("Unexpected response format");
    bookings.value = data
      .filter((booking) => booking.status === "pending")
      .sort((a, b) => String(a.startDatetime || "").localeCompare(String(b.startDatetime || "")));
  } catch (err) {
    error.value = err.response?.data?.error || "Could not load pending booking requests.";
  } finally {
    loading.value = false;
  }
}

onMounted(loadPendingBookings);
</script>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.page-title { margin: 0; font-size: 1.5rem; font-weight: 600; color: var(--text, #2d2a4a); }
.intro { margin: 0 0 1rem; color: var(--text-muted, #6b6890); }
.card { padding: 1.25rem 1.5rem; background: var(--surface, #fff); border: 1px solid var(--border, #e4defa); border-radius: 14px; box-shadow: 0 4px 16px rgba(109, 91, 208, 0.08); }
.summary { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.summary-label { font-weight: 600; color: var(--text, #2d2a4a); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 1rem; }
.booking header { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.5rem; }
.booking h3 { margin: 0 0 0.4rem; font-size: 1.1rem; color: var(--text, #2d2a4a); }
.meta { margin: 0.2rem 0; color: var(--text-muted, #6b6890); font-size: 0.92rem; }
.meta strong { color: var(--text, #2d2a4a); font-weight: 600; }
.desc { color: var(--text, #2d2a4a); margin: 0.75rem 0 0; padding-top: 0.75rem; border-top: 1px solid var(--border, #e4defa); }
.chips { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; margin-top: 0.7rem; }
.badge { padding: 0.15rem 0.6rem; border-radius: 999px; font-size: 0.82rem; font-weight: 500; white-space: nowrap; }
.cap { background: var(--butter-bg, #fef3c7); color: var(--butter-text, #92400e); }
.sky { background: var(--sky-bg, #e3f2ff); color: var(--sky-text, #356b99); }
.lilac { background: var(--lilac-bg, #e9e5fb); color: var(--lilac-text, #4b3fa0); }
.btn-primary { padding: 0.5rem 1.2rem; border: none; border-radius: 999px; font: inherit; font-weight: 500; background: var(--primary, #6d5bd0); color: #fff; cursor: pointer; }
.btn-primary:hover { background: var(--primary-hover, #5b49bd); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary:focus-visible { outline: 2px solid var(--primary, #6d5bd0); outline-offset: 2px; }
.field-error { color: #a12b47; font-size: 0.875rem; }
.empty { padding: 1rem; color: var(--text-muted, #6b6890); }
@media (max-width: 560px) { .head { flex-wrap: wrap; } .summary { flex-wrap: wrap; } }
</style>
