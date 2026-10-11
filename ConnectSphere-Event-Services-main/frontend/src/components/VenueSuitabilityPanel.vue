<template>
  <section class="suitability">
    <div class="head">
      <h3 class="section-title">Venue Suitability</h3>
      <span v-if="loading" class="muted small">Checking…</span>
    </div>

    <p v-if="loadError" class="field-error">{{ loadError }}</p>

    <template v-if="data">
      <!-- What every venue is checked against -->
      <div class="card requirements">
        <div class="req">
          <span class="detail-label">Expected attendance</span>
          <span>{{ data.requirements.expectedAttendance ?? "Not recorded" }}</span>
        </div>
        <div class="req">
          <span class="detail-label">Required layout</span>
          <span>
            {{ data.requirements.requiredLayoutLabel || data.requirements.requiredLayout || "None" }}
          </span>
        </div>
        <div class="req wide">
          <span class="detail-label">Accessibility requirements</span>
          <span v-if="data.requirements.accessibilityRequirements.length" class="chips">
            <span v-for="r in data.requirements.accessibilityRequirements" :key="r.code" class="chip">{{ r.label }}</span>
          </span>
          <span v-else>None</span>
        </div>
        <p v-if="data.requirements.accessibilityNotes" class="notes">
          <span class="detail-label">Organiser's notes (not checked automatically):</span>
          {{ data.requirements.accessibilityNotes }}
        </p>
      </div>

      <p v-if="!data.venues.length" class="muted">No active venues are in the catalogue yet.</p>

      <!-- One card per venue -->
      <div v-for="v in data.venues" :key="v.venue.id" class="card venue">
        <div class="venue-head">
          <div>
            <strong>{{ v.venue.name }}</strong>
            <span class="muted small"><template v-if="v.venue.location"> · {{ v.venue.location }}</template> · capacity {{ v.venue.capacity ?? "not recorded" }}</span>
          </div>
          <span class="badge" :class="v.overallStatus">{{ v.overallLabel }}</span>
        </div>

        <ul class="checks">
          <li v-for="c in v.checks" :key="c.type" :class="['check', c.status]">
            <div class="check-row">
              <span class="check-title">{{ c.title }}</span>
              <span class="badge" :class="c.status">{{ c.statusLabel }}</span>
              <button
                v-if="c.canOverride && data.isAssignedCoordinator && !isOpen(v.venue.id, c.type)"
                class="btn btn-grey btn-small"
                @click="openOverride(v.venue.id, c.type)"
              >
                Override
              </button>
            </div>
            <ul v-if="c.reasons.length" class="reasons">
              <li v-for="(r, i) in c.reasons" :key="i">{{ r }}</li>
            </ul>
            <p v-if="c.override" class="override-meta">
              Overridden by {{ c.override.overriddenByName }} on {{ fmt(c.override.createdAt) }}:
              “{{ c.override.reason }}”
            </p>

            <!-- Story 3: override with a mandatory reason -->
            <div v-if="isOpen(v.venue.id, c.type)" class="override-form">
              <textarea
                v-model="overrideForm.reason"
                :placeholder="`Why is this venue acceptable despite the ${c.title.toLowerCase()} flag? (e.g. extra chairs being brought in)`"
              ></textarea>
              <span class="small" :class="reasonLength >= minReason ? 'muted' : 'warn'">
                {{ reasonLength }} / {{ minReason }} characters minimum
              </span>
              <p v-if="overrideForm.error" class="field-error">{{ overrideForm.error }}</p>
              <div class="actions">
                <button class="btn btn-butter" :disabled="reasonLength < minReason || saving" @click="saveOverride(v.venue.id, c.type)">
                  Save override
                </button>
                <button class="btn btn-grey" @click="closeOverride">Cancel</button>
              </div>
            </div>
          </li>
        </ul>

        <!-- Booking goes through the Venue Booking Request page, which shows
             these flags again and refuses un-overridden unsuitable venues. -->
        <div v-if="data.isAssignedCoordinator" class="actions">
          <router-link
            v-if="!v.isBlocked"
            class="btn btn-primary"
            :to="{ name: 'venue-booking-request', query: { eventId: event.id, venueId: v.venue.id } }"
          >
            Request this venue
          </router-link>
          <span v-else class="muted small">Override every unsuitable flag before requesting this venue.</span>
        </div>
      </div>

      <!-- Story 3 AC3: audit trail visible on the event record -->
      <div v-if="data.overrideHistory.length" class="card history">
        <h4 class="block-title">Override history</h4>
        <ul class="history-list">
          <li v-for="h in data.overrideHistory" :key="h.id" :class="{ inactive: !h.isActive }">
            <span class="small">
              {{ fmt(h.createdAt) }} · {{ h.overriddenByName }} · {{ h.venueName }} · {{ titleFor(h.flagType) }}
              <em v-if="!h.isActive"> · cleared {{ fmt(h.clearedAt) }} ({{ h.clearedReason }})</em>
            </span>
            <span>“{{ h.reason }}”</span>
          </li>
        </ul>
      </div>
    </template>

  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import venuesApi from "../api/venues";

const props = defineProps({
  event: { type: Object, required: true },
});

const data = ref(null);
const loading = ref(false);
const loadError = ref("");
const saving = ref(false);
const minReason = ref(10);

const overrideForm = reactive({ venueId: null, flagType: null, reason: "", error: "" });

const TITLES = { capacity: "Capacity", accessibility: "Accessibility", layout: "Layout" };
const titleFor = (t) => TITLES[t] || t;
const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "");
const reasonLength = computed(() => overrideForm.reason.trim().length);

async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    const { data: body } = await venuesApi.suitability(props.event.id);
    data.value = body;
  } catch (e) {
    loadError.value = e.response?.data?.error || "Could not load venue suitability.";
  } finally {
    loading.value = false;
  }
}

// Story 1 AC4: suitability is recalculated server-side on every request, so
// re-fetch whenever the event's relevant details change on this page or the
// user comes back to the tab, with no manual refresh needed.
watch(
  () => [
    props.event.id,
    props.event.updatedAt,
    props.event.expectedAttendance,
    props.event.venueRequirements?.requiredLayout,
    JSON.stringify(props.event.venueRequirements?.accessibilityRequirements || []),
  ],
  load
);
const onFocus = () => document.visibilityState === "visible" && load();

onMounted(async () => {
  try {
    const { data: cat } = await venuesApi.suitabilityOptions();
    minReason.value = cat.minOverrideReasonLength || 10;
  } catch {
    /* keep default */
  }
  await load();
  window.addEventListener("focus", onFocus);
  document.addEventListener("visibilitychange", onFocus);
});
onBeforeUnmount(() => {
  window.removeEventListener("focus", onFocus);
  document.removeEventListener("visibilitychange", onFocus);
});

const isOpen = (venueId, flagType) => overrideForm.venueId === venueId && overrideForm.flagType === flagType;
function openOverride(venueId, flagType) {
  Object.assign(overrideForm, { venueId, flagType, reason: "", error: "" });
}
function closeOverride() {
  Object.assign(overrideForm, { venueId: null, flagType: null, reason: "", error: "" });
}

async function saveOverride(venueId, flagType) {
  overrideForm.error = "";
  saving.value = true;
  try {
    await venuesApi.overrideFlag(props.event.id, venueId, flagType, overrideForm.reason);
    closeOverride();
    await load();
  } catch (e) {
    overrideForm.error = e.response?.data?.error || "Could not save the override.";
  } finally {
    saving.value = false;
  }
}

</script>

<style scoped>
.suitability { margin-top: 1.5rem; }
.head { display: flex; align-items: baseline; gap: 0.75rem; }
.section-title { margin: 0 0 0.5rem; font-size: 1.1rem; font-weight: 600; color: var(--text, #2d2a4a); }
.block-title { margin: 0 0 0.5rem; font-size: 1rem; font-weight: 600; }
.muted { color: var(--text-muted, #6b6890); }
.small { font-size: 0.82rem; }
.warn { color: var(--rose-text, #a12b47); }
.field-error { margin: 0; color: var(--rose-text, #a12b47); font-size: 0.85rem; }

.card {
  margin-top: 0.75rem;
  padding: 1rem 1.25rem;
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e4defa);
  border-radius: 14px;
  box-shadow: 0 4px 16px rgba(109, 91, 208, 0.06);
}

.requirements { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 0.75rem; }
.req { display: flex; flex-direction: column; gap: 0.15rem; font-weight: 500; }
.req.wide { grid-column: span 2; }
.detail-label { font-size: 0.8rem; font-weight: 400; color: var(--text-muted, #6b6890); }
.notes { grid-column: 1 / -1; margin: 0; font-size: 0.9rem; }
.chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.chip { padding: 0.1rem 0.55rem; border-radius: 999px; background: var(--lilac-bg, #e9e5fb); color: var(--lilac-text, #4b3fa0); font-size: 0.82rem; }

.venue-head { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.checks { list-style: none; margin: 0.75rem 0; padding: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.check { padding: 0.55rem 0.75rem; border-radius: 10px; background: #faf9ff; }
.check.unsuitable { background: #fff5f7; }
.check.overridden { background: #fffbea; }
.check-row { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
.check-title { font-weight: 600; min-width: 7rem; }
.reasons { margin: 0.35rem 0 0; padding-left: 1.2rem; font-size: 0.9rem; }
.override-meta { margin: 0.35rem 0 0; font-size: 0.85rem; font-style: italic; }
.override-form { display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.5rem; }

.badge {
  display: inline-block; padding: 0.15rem 0.65rem; border-radius: 999px; font-size: 0.8rem; font-weight: 500; white-space: nowrap;
  background: var(--mint-bg, #d3f5e3); color: var(--mint-text, #1e6b47);
}
.badge.unsuitable { background: var(--rose-bg, #ffdce3); color: var(--rose-text, #a12b47); }
.badge.overridden { background: var(--butter-bg, #fff1c2); color: var(--butter-text, #8a5a00); }
.badge.not_verified { background: #e2e5ea; color: #55585e; }

.history-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.history-list li { display: flex; flex-direction: column; gap: 0.15rem; padding: 0.5rem 0.75rem; border-radius: 10px; background: var(--sky-bg, #d6ecff); }
.history-list li.inactive { opacity: 0.65; }


.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }
textarea, input { padding: 0.55rem 0.7rem; border: 1px solid var(--border, #e4defa); border-radius: 10px; font: inherit; }
textarea { min-height: 4rem; resize: vertical; }
label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.85rem; font-weight: 500; }

.btn { padding: 0.45rem 1rem; border: none; border-radius: 999px; font: inherit; font-size: 0.88rem; font-weight: 500; cursor: pointer; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-small { padding: 0.2rem 0.6rem; font-size: 0.8rem; }
.btn-primary { background: var(--primary, #6d5bd0); color: #fff; text-decoration: none; display: inline-block; }
.btn-butter { background: var(--butter-bg, #fff1c2); color: var(--butter-text, #8a5a00); }
.btn-grey { background: #c6cfd7; color: #626364; }

</style>
