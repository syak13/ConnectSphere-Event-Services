import apiClient from "./client";

export default {
  // Get all venues
  listVenues: () => apiClient.get("/venues"),

  // Submit one booking request with one or more venues
  submitBooking: (payload) => apiClient.post("/venues/bookings", payload),
};