import apiClient from "./client";

function toSearchQuery(criteria) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(criteria)) {
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else if (value !== "" && value !== null && value !== undefined) {
      params.append(key, value);
    }
  }
  return params.toString();
}

export default {
  // Get all venues
  listVenues: () => apiClient.get("/venues"),

  // Venue catalogue (Venue Staff manage; Event Coordinators read)
  getVenue: (id) => apiClient.get(`/venues/${id}`),
  create: (payload) => apiClient.post("/venues", payload),
  update: (id, payload) => apiClient.put(`/venues/${id}`, payload),
  deactivate: (id) => apiClient.delete(`/venues/${id}`),

  // Availability calendar
  getCalendar: (id, start, end) =>
    apiClient.get(`/venues/${id}/calendar`, { params: { start, end } }),
  getCombinedCalendar: (start, end) =>
    apiClient.get("/venues/calendar", { params: { start, end } }),
  addUnavailability: (id, payload) => apiClient.post(`/venues/${id}/unavailability`, payload),
  removeUnavailability: (id, blockId) =>
    apiClient.delete(`/venues/${id}/unavailability/${blockId}`),
  myFlags: () => apiClient.get("/venues/flags/mine"),
  resolveFlag: (id) => apiClient.post(`/venues/flags/${id}/resolve`),

  // Search venues by event criteria and catalogue filters
  search: (criteria) => apiClient.get(`/venues/search?${toSearchQuery(criteria)}`),

  // Get catalogue-backed values for the search filters
  searchOptions: () => apiClient.get("/venues/search/options"),

  // Submit one booking request with one or more venues
  submitBooking: (payload) => apiClient.post("/venues/bookings", payload),

  // Coordinator's own booking requests, and withdrawing a pending one
  getMyBookings: () => apiClient.get("/venues/bookings/my"),
  withdrawBooking: (bookingId) =>
    apiClient.post(`/venues/bookings/${bookingId}/withdraw`),
};
