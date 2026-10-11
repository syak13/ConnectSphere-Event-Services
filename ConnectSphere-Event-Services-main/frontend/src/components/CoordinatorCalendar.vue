<template>
  <div class="coordinator-calendar">
    <h2>My Calendar</h2>

    <label>
      <input type="checkbox" v-model="showReadOnly" />
      Show reassigned (read-only) events
    </label>

    <ul class="event-list">
      <li
        v-for="event in visibleEvents"
        :key="event.id"
        class="event-row"
        :class="{ 'read-only': event.isReadOnly }"
      >
        <span class="event-name">{{ event.name }}</span>
        <span class="event-date">{{ event.proposedDate }} {{ event.proposedTime }}</span>
        <span v-if="event.isReadOnly" class="badge read-only-badge">
          Reassigned — now coordinated by {{ event.coordinatorName || `user #${event.coordinatorId}` }}
        </span>
        <router-link :to="`/events/${event.id}`">View</router-link>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import eventsApi from "../api/events";

const events = ref([]);
const showReadOnly = ref(true);

async function load() {
  // The backend is the source of truth for isReadOnly — every write route
  // (reassign, approve, reject, status change) already enforces
  // "only the current Coordinator" server-side, so there's no separate
  // edit-check call needed here; this flag just drives what the UI shows.
  const { data } = await eventsApi.coordinatorCalendar();
  events.value = data;
}

const visibleEvents = computed(() =>
  showReadOnly.value ? events.value : events.value.filter((e) => !e.isReadOnly)
);

onMounted(load);
</script>
