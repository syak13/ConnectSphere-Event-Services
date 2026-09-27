import apiClient from "./client";

export default {
  createEvent: (payload) => apiClient.post("/events", payload),
  saveDraft: (payload) => apiClient.post("/events/drafts", payload),
  listDrafts: () => apiClient.get("/events/drafts"),
  updateDraft: (id, payload) => apiClient.put(`/events/drafts/${id}`, payload),
  deleteDraft: (id) => apiClient.delete(`/events/drafts/${id}`),
  submitEvent: (id) => apiClient.post(`/events/${id}/submit`),
  myEvents: () => apiClient.get("/events/mine"),
  assignedEvents: () => apiClient.get("/events/assigned"),
  allEvents: () => apiClient.get("/events"),
  getEvent: (id) => apiClient.get(`/events/${id}`),
  getOutcome: (id) => apiClient.get(`/events/${id}/outcome`),
  requestClarification: (id, comments, editableFields = []) => apiClient.post(`/events/${id}/clarification`, { comments, editableFields }),
  respondClarification: (id, payload) => apiClient.post(`/events/${id}/clarification/response`, payload),
  approveEvent: (id, comments) => apiClient.post(`/events/${id}/approve`, { comments }),
  rejectEvent: (id, reason) => apiClient.post(`/events/${id}/reject`, { reason }),
  resubmitEvent: (id, payload) => apiClient.post(`/events/${id}/resubmit`, payload),
  reassign: (id, newCoordinatorId) => apiClient.post(`/events/${id}/reassign`, { newCoordinatorId }),
  changeStatus: (id, statusValue, reason) => apiClient.post(`/events/${id}/status`, { status: statusValue, reason }),
};
