import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

import LoginView from "../views/LoginView.vue";
import DashboardView from "../views/DashboardView.vue";
import DraftsView from "../views/DraftsView.vue";
import EventCreateView from "../views/EventCreateView.vue";
import ReviewQueueView from "../views/ReviewQueueView.vue";
import EventDetailView from "../views/EventDetailView.vue";


const routes = [
  { path: "/login", name: "login", component: LoginView },
  {
    // No roles list: any logged-in user can open the dashboard
    path: "/",
    name: "dashboard",
    component: DashboardView,
    meta: { requiresAuth: true },
  },
  {
    path: "/drafts",
    name: "drafts",
    component: DraftsView,
    meta: { requiresAuth: true, roles: ["event_organiser"] },
  },
  {
    path: "/events/new",
    name: "event-create",
    component: EventCreateView,
    meta: { requiresAuth: true, roles: ["event_organiser"] },
  },
  {
    path: "/review",
    name: "review-queue",
    component: ReviewQueueView,
    meta: { requiresAuth: true, roles: ["event_coordinator"] },
  },
  {
    path: "/events/:id",
    name: "event-detail",
    component: EventDetailView,
    meta: { requiresAuth: true, roles: ["event_organiser", "event_coordinator"] },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuthStore();

  // Not logged in -> login page
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "login" };
  }

  // If the route lists roles, the user needs at least one of them
  if (to.meta.roles && !to.meta.roles.some((r) => auth.hasRole(r))) {
    return { name: "dashboard" };
  }
});

export default router;