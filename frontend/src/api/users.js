import apiClient from "./client";

export default {
  // Added: backs the Coordinator picker in the reassignment flow.
  listCoordinators: () => apiClient.get("/auth/users", { params: { role: "event_coordinator" } }),
};
