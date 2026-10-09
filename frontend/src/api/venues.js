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

  // Search venues by event criteria and catalogue filters
  search: (criteria) => apiClient.get(`/venues/search?${toSearchQuery(criteria)}`),

  // Get catalogue-backed values for the search filters
  searchOptions: () => apiClient.get("/venues/search/options"),

  // Submit one booking request with one or more venues
  submitBooking: (payload) => apiClient.post("/venues/bookings", payload),

  getMyBookings: () => apiClient.get("/venues/bookings/my"),

  withdrawBooking: (bookingId) =>
    apiClient.post(`/venues/bookings/${bookingId}/withdraw`),
};