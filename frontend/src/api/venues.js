import apiClient from "./client";

function toSearchQuery(criteria) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(criteria)) {
    if (value !== "" && value !== null && value !== undefined) {
      params.append(key, value);
    }
  }
  return params.toString();
}

export default {
  // Get all venues
  listVenues: () => apiClient.get("/venues"),

  // Search venues by date, time window, and expected attendance
  search: (criteria) => apiClient.get(`/venues/search?${toSearchQuery(criteria)}`),

  // Submit one booking request with one or more venues
  submitBooking: (payload) => apiClient.post("/venues/bookings", payload),

  getMyBookings: () => apiClient.get("/venues/bookings/my"),
};