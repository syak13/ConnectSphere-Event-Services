<template>
  <div>
    <h2>{{ auth.hasRole("event_coordinator") ? "Events Assigned to Me" : "My Events" }}</h2>
    <table v-if="events.length">
      <thead>
        <tr>
          <th>Name</th>
          <th>Status</th>
          <th>Proposed Date/Time</th>
          <th>Venue Reqs.</th>
          <th v-if="auth.hasRole('event_coordinator')">Organiser</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in events" :key="e.id">
          <td>{{ e.name || "(untitled)" }}</td>
          <td><span class="badge" :class="e.status">{{ e.status }}</span></td>
          <td>{{ e.proposedDate || "—" }} {{ e.proposedTime || "" }}</td>
          <td>{{ venueSummary(e) }}</td>
          <td v-if="auth.hasRole('event_coordinator')">{{ e.organiserName || "—" }}</td>
          <td><router-link :to="`/events/${e.id}`">View</router-link></td>
        </tr>
      </tbody>
    </table>
    <p v-else>No events yet.</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useAuthStore } from "../stores/auth";
import eventsApi from "../api/events";

const auth = useAuthStore();
const events = ref([]);

// Summary for the "Venue Reqs." column — this project doesn't have an actual
// booked-venue entity yet (only what the Organiser requested), so this shows
// requirements, not a confirmed venue.
function venueSummary(e) {
  const v = e.venueRequirements;
  if (!v || (!v.capacityNeeded && !v.requiredLayout)) return "—";
  return [v.capacityNeeded ? `${v.capacityNeeded} pax` : null, v.requiredLayout].filter(Boolean).join(", ");
}

onMounted(async () => {
  const call = auth.hasRole("event_coordinator") ? eventsApi.assignedEvents : eventsApi.myEvents;
  const { data } = await call();
  events.value = data;
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
.badge.approved, .badge.confirmed, .badge.completed { background: #d7f5dd; }
.badge.rejected, .badge.cancelled { background: #fbdcdc; }
.badge.under_review, .badge.submitted, .badge.planning { background: #fff3cd; }
</style>
