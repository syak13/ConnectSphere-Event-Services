<template>
    <div>
        <h2 class="page-title">Submit Venue Booking Request</h2>

        <div class="card">
            <form @submit.prevent="submitBooking">

                <!-- EVENT -->
                <div class="section">
                    <h3>Event</h3>

                    <!-- EVENT SELECTION -->
                    <div class="form-group">
                        <label for="event">Select Event *</label>

                        <select id="event" v-model="eventId" required>
                            <option value="" disabled>
                                Select an event
                            </option>

                            <option v-for="event in events" :key="event.id" :value="event.id">
                                {{ event.name || event.title || `Event ${event.id}` }}
                            </option>
                        </select>
                    </div>

                    <!-- SELECTED EVENT REQUIREMENTS -->
                    <div v-if="selectedEvent" class="requirements-box">
                        <h4>Event Venue Requirements</h4>

                        <div class="requirements-grid">
                            <div>
                                <span class="requirement-label">
                                    Capacity Needed
                                </span>
                                <span>
                                    {{ selectedEvent.venueRequirements?.capacityNeeded || "Not specified" }}
                                </span>
                            </div>

                            <div>
                                <span class="requirement-label">
                                    Required Layout
                                </span>
                                <span>
                                    {{ selectedEvent.venueRequirements?.requiredLayout || "Not specified" }}
                                </span>
                            </div>

                            <div>
                                <span class="requirement-label">
                                    Accessibility Needs
                                </span>
                                <span>
                                    {{ selectedEvent.venueRequirements?.accessibilityNeeds || "Not specified" }}
                                </span>
                            </div>

                            <div>
                                <span class="requirement-label">
                                    Required Facilities
                                </span>
                                <span>
                                    {{
                                        selectedEvent.venueRequirements?.requiredFacilities?.length
                                            ? selectedEvent.venueRequirements.requiredFacilities.join(", ")
                                    : "Not specified"
                                    }}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- VENUES -->
                <div class="section">
                    <div class="section-heading">
                        <div>
                            <h3>Venues</h3>

                            <p class="section-description">
                                Add one or more venues for this event.
                                Each venue can have its own booking timing.
                            </p>
                        </div>

                        <button type="button" class="btn secondary" @click="addVenue">
                            + Add Venue
                        </button>
                    </div>

                    <!-- ONE CARD PER VENUE -->
                    <div v-for="(venueRequest, index) in venueRequests" :key="index" class="venue-card">
                        <div class="venue-heading">
                            <h4>Venue {{ index + 1 }}</h4>

                            <button v-if="venueRequests.length > 1" type="button" class="remove-btn"
                                @click="removeVenue(index)">
                                Remove
                            </button>
                        </div>

                        <!-- VENUE SELECTION -->
                        <div class="form-group">
                            <label :for="`venue-${index}`">
                                Venue *
                            </label>

                            <select :id="`venue-${index}`" v-model="venueRequest.venueId" required>
                                <option value="" disabled>
                                    Select a venue
                                </option>

                                <option v-for="venue in availableVenues(index)" :key="venue.id" :value="venue.id">
                                    {{ venue.name }}
                                </option>
                            </select>

                            <p v-if="fieldError(index, 'venue_id')" class="field-error">
                                {{ fieldError(index, "venue_id") }}
                            </p>
                        </div>

                        <!-- TIMING -->
                        <h5 class="subheading">Timing</h5>

                        <div class="form-grid">

                            <!-- DATE -->
                            <div class="form-group">
                                <label :for="`date-${index}`">
                                    Date *
                                </label>

                                <input :id="`date-${index}`" v-model="venueRequest.date" type="date" :min="today"
                                    required />

                                <p v-if="fieldError(index, 'date')" class="field-error">
                                    {{ fieldError(index, "date") }}
                                </p>
                            </div>

                            <!-- START TIME -->
                            <div class="form-group">
                                <label :for="`start-${index}`">
                                    Start Time *
                                </label>

                                <input :id="`start-${index}`" v-model="venueRequest.startTime" type="time" required />

                                <p v-if="fieldError(index, 'start_time')" class="field-error">
                                    {{ fieldError(index, "start_time") }}
                                </p>
                            </div>

                            <!-- END DATE -->
                            <div class="form-group">
                                <label :for="`end-date-${index}`">
                                    End Date
                                </label>

                                <input :id="`end-date-${index}`" v-model="venueRequest.endDate" type="date"
                                    :min="venueRequest.date || today" />

                                <p class="hint">
                                    Only needed if the booking ends on another day.
                                </p>

                                <p v-if="fieldError(index, 'end_date')" class="field-error">
                                    {{ fieldError(index, "end_date") }}
                                </p>
                            </div>

                            <!-- END TIME -->
                            <div class="form-group">
                                <label :for="`end-${index}`">
                                    End Time *
                                </label>

                                <input :id="`end-${index}`" v-model="venueRequest.endTime" type="time" required />

                                <p v-if="fieldError(index, 'end_time')" class="field-error">
                                    {{ fieldError(index, "end_time") }}
                                </p>
                            </div>
                        </div>
                    </div>

                    <!-- GENERAL ERROR -->
                    <div v-if="generalErrors.length" class="error-message">
                        <p v-for="(error, index) in generalErrors" :key="index">
                            {{ error }}
                        </p>
                    </div>
                </div>

                <!-- BUTTONS -->
                <div class="actions">
                    <button type="button" class="btn secondary" @click="resetForm">
                        Clear
                    </button>

                    <button type="submit" class="btn" :disabled="submitting">
                        {{
                            submitting
                                ? "Submitting..."
                                : "Submit Booking Request"
                        }}
                    </button>
                </div>
            </form>
        </div>

        <!-- SUCCESS -->
        <div v-if="successMessage" class="success-message">
            {{ successMessage }}
        </div>
    </div>
</template>


<script setup>
import { computed, onMounted, ref } from "vue";

import eventsApi from "../api/events";
import venuesApi from "../api/venues";


const events = ref([]);
const venues = ref([]);

const eventId = ref("");

const submitting = ref(false);

const errors = ref([]);

const successMessage = ref("");

const selectedEvent = computed(() => {
    return events.value.find(
        (event) => Number(event.id) === Number(eventId.value)
    );
});

const today = new Date().toISOString().split("T")[0];


/*
 * Creates a blank venue entry.
 */
const emptyVenue = () => ({
    venueId: "",
    date: "",
    startTime: "",
    endTime: "",
    endDate: "",
});


const venueRequests = ref([
    emptyVenue(),
]);


/*
 * Prevent the same venue from being selected
 * more than once in the same request.
 */
function availableVenues(currentIndex) {
    const selectedIds = venueRequests.value
        .map((request, index) => {
            if (index === currentIndex) {
                return null;
            }

            return Number(request.venueId);
        })
        .filter(Boolean);

    return venues.value.filter(
        (venue) => !selectedIds.includes(Number(venue.id))
    );
}


/*
 * Add another venue to the request.
 */
function addVenue() {
    venueRequests.value.push(
        emptyVenue()
    );
}


/*
 * Remove a venue.
 */
function removeVenue(index) {
    venueRequests.value.splice(index, 1);

    // Clear old backend errors because
    // the venue positions have changed.
    errors.value = [];
}


/*
 * Reset the entire form.
 */
function resetForm() {
    eventId.value = "";

    venueRequests.value = [
        emptyVenue(),
    ];

    errors.value = [];

    successMessage.value = "";
}


/*
 * Find the backend validation error
 * belonging to a particular venue field.
 */
function fieldError(index, field) {
    const request =
        venueRequests.value[index];

    const matchingError =
        errors.value.find((error) => {

            if (error.field !== field) {
                return false;
            }

            /*
             * Backend normally returns venue_id.
             */
            if (error.venue_id != null) {
                return (
                    Number(error.venue_id) ===
                    Number(request.venueId)
                );
            }

            /*
             * Fallback for errors where the
             * venue ID could not be determined.
             */
            return (
                error.venue ===
                `Venue ${index + 1}`
            );
        });

    return matchingError?.message || "";
}


/*
 * Errors not tied to a particular
 * venue field.
 */
const generalErrors = computed(() => {
    return errors.value
        .filter((error) => {
            return error.field === "venues";
        })
        .map((error) => error.message);
});


/*
 * Submit the booking request.
 */
async function submitBooking() {
    errors.value = [];
    successMessage.value = "";

    if (!eventId.value) {
        errors.value = [
            {
                field: "venues",
                message: "Please select an event.",
            },
        ];

        return;
    }

    submitting.value = true;

    try {

        /*
         * Payload matches routes.py:
         *
         * {
         *   eventId: ...,
         *   venues: [...]
         * }
         */
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


        await venuesApi.submitBooking(
            payload
        );


        successMessage.value =
            "Venue booking request submitted successfully.";


        /*
         * Keep the selected event but
         * clear the venue form.
         *
         * This makes it easy for the
         * coordinator to see which event
         * they just submitted for.
         */
        venueRequests.value = [
            emptyVenue(),
        ];

    } catch (error) {

        const data =
            error.response?.data;


        /*
         * Backend returns field-specific
         * validation errors.
         */
        if (
            Array.isArray(data?.errors)
        ) {
            errors.value =
                data.errors;

        } else {

            errors.value = [
                {
                    field: "venues",

                    message:
                        data?.error ||
                        "Unable to submit the booking request.",
                },
            ];
        }

    } finally {
        submitting.value = false;
    }
}


/*
 * Load coordinator events and venues
 * when the page opens.
 */
onMounted(async () => {
    try {
        const eventsResponse = await eventsApi.assignedEvents();
        console.log("Events loaded:", eventsResponse.data);

        events.value = eventsResponse.data;
    } catch (error) {
        console.error("EVENTS ERROR:", error);
    }

    try {
        const venuesResponse = await venuesApi.listVenues();
        console.log("Venues loaded:", venuesResponse.data);

        venues.value = venuesResponse.data;
    } catch (error) {
        console.error("VENUES ERROR:", error);
    }
});
</script>


<style scoped>
.page-title {
    margin: 0 0 1rem;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text, #2d2a4a);
}


.card {
    background: var(--surface, #ffffff);

    border:
        1px solid var(--border, #e4defa);

    border-radius: 14px;

    box-shadow:
        0 4px 16px rgba(109, 91, 208, 0.08);

    overflow: hidden;
}


.section {
    padding: 1.25rem;

    border-bottom:
        1px solid var(--border, #e4defa);
}


.section:last-child {
    border-bottom: none;
}


.section h3 {
    margin: 0 0 1rem;

    color:
        var(--text, #2d2a4a);

    font-size: 1.1rem;

    font-weight: 600;
}


.section-heading {
    display: flex;

    align-items: flex-start;

    justify-content:
        space-between;

    gap: 1rem;

    margin-bottom: 1rem;
}


.section-heading h3 {
    margin-bottom: 0.25rem;
}


.section-description {
    margin: 0;

    color:
        var(--text-muted, #6b6890);

    font-size: 0.9rem;
}


.venue-card {
    margin-top: 1rem;

    padding: 1.25rem;

    background: #faf9ff;

    border:
        1px solid var(--border, #e4defa);

    border-radius: 12px;
}


.venue-heading {
    display: flex;

    justify-content:
        space-between;

    align-items: center;

    margin-bottom: 1rem;
}


.venue-heading h4 {
    margin: 0;

    color:
        var(--lilac-text, #4b3fa0);

    font-size: 1rem;
}


.subheading {
    margin:
        1rem 0 0.8rem;

    color:
        var(--text, #2d2a4a);

    font-size: 0.95rem;

    font-weight: 600;
}


.form-group {
    display: flex;

    flex-direction: column;

    gap: 0.35rem;

    margin-bottom: 1rem;
}


.form-grid {
    display: grid;

    grid-template-columns:
        repeat(2, 1fr);

    gap: 0 1rem;
}


label {
    color:
        var(--text, #2d2a4a);

    font-size: 0.875rem;

    font-weight: 500;
}


input,
select,
textarea {
    width: 100%;

    box-sizing:
        border-box;

    padding:
        0.65rem 0.75rem;

    border:
        1px solid var(--border, #e4defa);

    border-radius: 8px;

    background: #ffffff;

    color:
        var(--text, #2d2a4a);

    font: inherit;
}


textarea {
    resize: vertical;
}


input:focus,
select:focus,
textarea:focus {
    outline:
        2px solid var(--primary, #6d5bd0);

    outline-offset: 1px;

    border-color:
        var(--primary, #6d5bd0);
}


.hint {
    margin: 0;

    color:
        var(--text-muted, #6b6890);

    font-size: 0.78rem;
}


.field-error {
    margin: 0.25rem 0 0;

    color:
        var(--rose-text, #a12b47);

    font-size: 0.85rem;
}


.error-message {
    margin-top: 1rem;

    padding: 0.8rem 1rem;

    background:
        var(--rose-bg, #fde8ee);

    color:
        var(--rose-text, #a12b47);

    border-radius: 8px;

    font-size: 0.875rem;
}


.error-message p {
    margin: 0.2rem 0;
}


.success-message {
    margin-top: 1rem;

    padding: 0.9rem 1rem;

    border-radius: 10px;

    background:
        var(--mint-bg, #d3f5e3);

    color:
        var(--mint-text, #1e6b47);

    font-weight: 500;
}


.actions {
    display: flex;

    justify-content: flex-end;

    gap: 0.75rem;

    padding: 1.25rem;
}


.btn {
    display: inline-block;

    padding:
        0.55rem 1.1rem;

    border: none;

    border-radius: 999px;

    background:
        var(--primary, #6d5bd0);

    color: #ffffff;

    font: inherit;

    font-weight: 500;

    cursor: pointer;
}


.btn:hover:not(:disabled) {
    background:
        var(--primary-hover, #5b49bd);
}


.btn.secondary {
    background:
        var(--lilac-bg, #e9e5fb);

    color:
        var(--lilac-text, #4b3fa0);
}


.btn.secondary:hover {
    background: #ddd6fb;
}


.btn:disabled {
    opacity: 0.6;

    cursor: not-allowed;
}


.remove-btn {
    border: none;

    background: transparent;

    color:
        var(--rose-text, #a12b47);

    font: inherit;

    font-size: 0.85rem;

    font-weight: 500;

    cursor: pointer;
}

.remove-btn:hover {
    text-decoration: underline;
}

.requirements-box {
    margin-top: 1rem;
    padding: 1rem;
    background: #faf9ff;
    border: 1px solid var(--border, #e4defa);
    border-radius: 10px;
}

.requirements-box h4 {
    margin: 0 0 0.8rem;
    color: var(--lilac-text, #4b3fa0);
    font-size: 0.95rem;
}

.requirements-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.8rem 1.5rem;
}

.requirements-grid>div {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
}

.requirement-label {
    color: var(--text-muted, #6b6890);
    font-size: 0.78rem;
    font-weight: 500;
}

@media (max-width: 700px) {
    .form-grid {
        grid-template-columns: 1fr;
    }


    .section-heading {
        flex-direction: column;
    }


    .actions {
        flex-direction: column-reverse;
    }


    .actions .btn {
        width: 100%;
    }

    .requirements-grid {
        grid-template-columns: 1fr;
    }
}
</style>