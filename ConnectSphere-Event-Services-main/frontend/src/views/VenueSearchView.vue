<template>
  <section>
    <h2 class="page-title">Venue Search</h2>

    <form class="card search-form" @submit.prevent="search">
      <h3>Find available venues</h3>
      <div class="fields">
        <label>
          Date
          <input v-model="criteria.date" type="date" :aria-invalid="!!errors.date" />
          <span v-if="errors.date" class="field-error">{{ errors.date }}</span>
        </label>
        <label>
          Start time
          <input v-model="criteria.start_time" type="time" :aria-invalid="!!errors.start_time" />
          <span v-if="errors.start_time" class="field-error">{{ errors.start_time }}</span>
        </label>
        <label>
          End time
          <input v-model="criteria.end_time" type="time" :aria-invalid="!!errors.end_time" />
          <span v-if="errors.end_time" class="field-error">{{ errors.end_time }}</span>
        </label>
        <label>
          Expected attendance
          <input
            v-model="criteria.attendance"
            type="text"
            inputmode="numeric"
            :aria-invalid="!!errors.attendance"
          />
          <span v-if="errors.attendance" class="field-error">{{ errors.attendance }}</span>
        </label>
      </div>

      <fieldset class="filter-panel">
        <legend>Filter results</legend>
        <div class="fields">
          <label>
            Location
            <select v-model="filters.location" @change="applyFilters">
              <option value="">All locations</option>
              <option v-for="location in filterOptions.locations" :key="location" :value="location">
                {{ location }}
              </option>
            </select>
          </label>
          <label>
            Maximum capacity
            <input
              v-model="filters.max_capacity"
              type="number"
              min="1"
              step="1"
              :aria-invalid="!!errors.max_capacity"
              @change="applyFilters"
            />
            <span v-if="errors.max_capacity" class="field-error">{{ errors.max_capacity }}</span>
          </label>
          <fieldset class="option-group">
            <legend>Accessibility features</legend>
            <p v-if="!filterOptions.accessibilityFeatures.length" class="filter-hint">
              No accessibility features are listed in the venue catalogue.
            </p>
            <label
              v-for="feature in filterOptions.accessibilityFeatures"
              :key="feature"
              class="option-label"
            >
              <input
                v-model="filters.accessibility"
                type="checkbox"
                :value="feature"
                @change="applyFilters"
              />
              {{ feature }}
            </label>
          </fieldset>
          <fieldset class="option-group">
            <legend>Facilities</legend>
            <p v-if="!filterOptions.facilities.length" class="filter-hint">
              No facilities are listed in the venue catalogue.
            </p>
            <label
              v-for="facility in filterOptions.facilities"
              :key="facility"
              class="option-label"
            >
              <input
                v-model="filters.facilities"
                type="checkbox"
                :value="facility"
                @change="applyFilters"
              />
              {{ facility }}
            </label>
          </fieldset>
        </div>
        <p v-if="filterOptionsError" class="field-error" role="alert">{{ filterOptionsError }}</p>
        <div class="filter-actions">
          <button type="button" :disabled="loading" @click="applyFilters">Apply filters</button>
          <button type="button" :disabled="loading" @click="clearFilters">Clear filters</button>
        </div>
      </fieldset>

      <p v-if="pageError" class="field-error" role="alert">{{ pageError }}</p>
      <button type="submit" :disabled="loading">
        {{ loading ? "Searching..." : "Search venues" }}
      </button>
    </form>

    <section v-if="results !== null" class="results" aria-live="polite">
      <h3>Results <span class="count">({{ results.length }})</span></h3>
      <p v-if="!results.length" class="empty">
        No venues match your filters.
      </p>
      <article v-for="venue in results" :key="venue.id" class="card venue-card">
        <h4>{{ venue.name }}</h4>
        <p><strong>Location:</strong> {{ venue.location || "Not specified" }}</p>
        <p><strong>Capacity:</strong> {{ venue.capacity }}</p>
        <p v-if="venue.accessibilityFeatures?.length">
          <strong>Accessibility:</strong> {{ venue.accessibilityFeatures.join(", ") }}
        </p>
        <p v-if="venue.facilities?.length">
          <strong>Facilities:</strong> {{ venue.facilities.join(", ") }}
        </p>
      </article>
    </section>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import venuesApi from "../api/venues";

const criteria = reactive({
  date: "",
  start_time: "",
  end_time: "",
  attendance: "",
});
const filters = reactive({
  location: "",
  max_capacity: "",
  accessibility: [],
  facilities: [],
});
const filterOptions = reactive({
  locations: [],
  accessibilityFeatures: [],
  facilities: [],
});
const filterOptionsError = ref("");
const errors = reactive({});
const results = ref(null);
const loading = ref(false);
const pageError = ref("");
const hasSearched = ref(false);
let searchSequence = 0;

function validate() {
  Object.keys(errors).forEach((key) => delete errors[key]);
  if (!criteria.date) errors.date = "Date is required.";
  if (!criteria.start_time) errors.start_time = "Start time is required.";
  if (!criteria.end_time) errors.end_time = "End time is required.";
  if (criteria.start_time && criteria.end_time && criteria.end_time <= criteria.start_time) {
    errors.end_time = "End time must be after start time.";
  }
  if (criteria.attendance === "" || criteria.attendance === null) {
    errors.attendance = "Expected attendance is required.";
  } else if (
    !/^[0-9]+$/.test(String(criteria.attendance)) ||
    Number(criteria.attendance) < 1
  ) {
    errors.attendance = "Enter a positive whole number.";
  }
  return Object.keys(errors).length === 0;
}

async function runSearch() {
  const sequence = ++searchSequence;
  pageError.value = "";
  if (!validate()) {
    results.value = null;
    loading.value = false;
    return;
  }

  hasSearched.value = true;
  loading.value = true;
  try {
    if (
      filters.max_capacity !== "" &&
      Number(filters.max_capacity) < Number(criteria.attendance)
    ) {
      errors.max_capacity = "Maximum capacity cannot be lower than expected attendance.";
      results.value = null;
      return;
    }
    delete errors.max_capacity;
    const { data } = await venuesApi.search({
      ...criteria,
      ...filters,
    });
    if (sequence === searchSequence) results.value = data;
  } catch (error) {
    if (sequence === searchSequence) {
      if (error.response?.data?.errors) {
        Object.assign(errors, error.response.data.errors);
        results.value = null;
      } else {
        results.value = null;
        pageError.value = error.response?.data?.error || "Could not search venues.";
      }
    }
  } finally {
    if (sequence === searchSequence) loading.value = false;
  }
}

function search() {
  return runSearch();
}

function applyFilters() {
  if (hasSearched.value) return runSearch();
}

function clearFilters() {
  filters.location = "";
  filters.max_capacity = "";
  filters.accessibility = [];
  filters.facilities = [];
  if (hasSearched.value) runSearch();
}

onMounted(async () => {
  try {
    const { data } = await venuesApi.searchOptions();
    Object.assign(filterOptions, data);
  } catch (error) {
    filterOptionsError.value =
      error.response?.data?.error || "Could not load venue filter options.";
  }
});

</script>

<style scoped>
.search-form,
.venue-card {
  margin-bottom: 1rem;
}

.fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-weight: 600;
}

input {
  box-sizing: border-box;
  width: 100%;
  min-height: 2.4rem;
  padding: 0.4rem;
  border: 1px solid var(--border);
  border-radius: 0.35rem;
  color: var(--text);
  background: var(--surface);
  font: inherit;
}

select {
  box-sizing: border-box;
  width: 100%;
  min-height: 2.4rem;
  padding: 0.4rem;
  border: 1px solid var(--border);
  border-radius: 0.35rem;
  color: var(--text);
  background: var(--surface);
  font: inherit;
}

.option-group {
  min-width: 0;
  margin: 0;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 0.35rem;
}

.option-group legend {
  padding: 0 0.25rem;
  font-weight: 600;
}

.fields .option-label {
  display: flex;
  flex-direction: row;
  align-items: center;
  margin: 0.35rem 0;
  font-weight: 400;
}

.fields .option-label input {
  width: auto;
  min-height: auto;
  margin: 0 0.5rem 0 0;
}

.filter-hint {
  margin: 0.25rem 0;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.filter-panel {
  margin: 1rem 0;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
}

.filter-actions {
  display: flex;
  gap: 0.75rem;
}

.field-error {
  color: #a12b47;
  font-size: 0.875rem;
}

input[aria-invalid="true"] {
  border-color: #a12b47;
}

.count {
  color: var(--text-muted);
  font-size: 0.9em;
}

.empty {
  padding: 1rem;
  color: var(--text-muted);
}

.venue-card h4 {
  margin: 0 0 0.5rem;
}

.venue-card p {
  margin: 0.25rem 0;
}

.page-title { margin: 0 0 1rem; font-size: 1.5rem; font-weight: 600; color: var(--text); }
.card {
  padding: 1.25rem 1.5rem; background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; box-shadow: 0 4px 16px rgba(109, 91, 208, 0.08);
}
button[type="submit"] {
  padding: 0.55rem 1.3rem; border: none; border-radius: 999px;
  background: var(--primary); color: #fff; font: inherit; font-weight: 500;
}
button[type="submit"]:disabled { opacity: 0.6; cursor: not-allowed; }


@media (max-width: 560px) {
  .fields {
    grid-template-columns: 1fr;
  }
}
</style>
