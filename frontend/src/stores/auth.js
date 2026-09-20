import { defineStore } from "pinia";
import apiClient from "../api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: localStorage.getItem("accessToken") || null,
    refreshToken: localStorage.getItem("refreshToken") || null,
    user: JSON.parse(localStorage.getItem("user") || "null"),
  }),
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    roles: (state) => state.user?.roles || [],
  },
  actions: {
    async login(email, password) {
      const { data } = await apiClient.post("/auth/login", { email, password });
      this.accessToken = data.accessToken;
      this.refreshToken = data.refreshToken;
      this.user = data.user;
      localStorage.setItem("accessToken", data.accessToken);
      localStorage.setItem("refreshToken", data.refreshToken);
      localStorage.setItem("user", JSON.stringify(data.user));
    },
    async logout() {
      try {
        await apiClient.post(
          "/auth/logout",
          {},
          { headers: { Authorization: `Bearer ${this.refreshToken}` } }
        );
      } finally {
        this.accessToken = null;
        this.refreshToken = null;
        this.user = null;
        localStorage.removeItem("accessToken");
        localStorage.removeItem("refreshToken");
        localStorage.removeItem("user");
      }
    },
    hasRole(role) {
      return this.roles.includes(role);
    },
  },
});
