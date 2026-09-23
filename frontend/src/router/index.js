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
    path: "/",
    name: "dashboard",
    component: DashboardView,
    meta: { requiresAuth: true },
  },

  {
    path: "/drafts",
    name: "drafts",
    component: DraftsView,
    meta: { requiresAuth: true },
  },

  {
    path: "/events/new",
    name: "event-create",
    component: EventCreateView,
    meta: { requiresAuth: true },
  },

  {
    path: "/events/drafts/:id/edit",
    name: "edit-draft",
    component: EventCreateView,
    meta: { requiresAuth: true, roles: ["event_organiser"] },
  },

  {
    path: "/review",
    name: "review-queue",
    component: ReviewQueueView,
    meta: { requiresAuth: true },
  },

  {
    path: "/events/:id",
    name: "event-detail",
    component: EventDetailView,
    meta: { requiresAuth: true },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuthStore();

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "login" };
  }

  if (to.meta.roles && !to.meta.roles.some((role) => auth.hasRole(role))) {
    return { name: "dashboard" };
  }
});

export default router;
