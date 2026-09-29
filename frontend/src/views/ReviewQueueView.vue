<template>
  <div>
    <h2>Review Queue</h2>
    <table v-if="events.length">
      <thead>
        <tr>
          <th>Name</th>
          <th>Status</th>
          <th>Proposed Date/Time</th>
          <th>Venue Reqs.</th>
          <th>Organiser</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in events" :key="e.id">
          <td>{{ e.name }}</td>
          <td><span class="badge" :class="e.status">{{ e.status }}</span></td>
          <td>{{ e.proposedDate || "—" }} {{ e.proposedTime || "" }}</td>
          <td>{{ venueSummary(e) }}</td>
          <td>{{ e.organiserName || "—" }}</td>
          <td><router-link :to="`/events/${e.id}`">Review</router-link></td>
        </tr>
      </tbody>
    </table>
    <p v-else>No assigned requests.</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import eventsApi from "../api/events";

const events = ref([]);

function venueSummary(e) {
  const v = e.venueRequirements;
  if (!v || (!v.capacityNeeded && !v.requiredLayout)) return "—";
  return [v.capacityNeeded ? `${v.capacityNeeded} pax` : null, v.requiredLayout].filter(Boolean).join(", ");
}

onMounted(async () => {
  const { data } = await eventsApi.assignedEvents();
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
.badge.approved { background: #d7f5dd; }
.badge.rejected { background: #fbdcdc; }
.badge.under_review { background: #fff3cd; }
</style>
