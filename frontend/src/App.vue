<template>
  <div id="layout">
    <nav v-if="auth.isAuthenticated">
      <router-link to="/">Dashboard</router-link>
      <router-link v-if="auth.hasRole('event_organiser')" to="/events/new">New Request</router-link>
      <router-link v-if="auth.hasRole('event_organiser')" to="/drafts">My Drafts</router-link>
      <router-link v-if="auth.hasRole('event_coordinator')" to="/review">Review Queue</router-link>
      <span class="spacer" />
      <span>{{ auth.user?.name }}</span>
      <button @click="handleLogout">Logout</button>
    </nav>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const router = useRouter();

async function handleLogout() {
  try {
    await auth.logout();
  } finally {
    router.replace({ name: "login" });
  }
}
</script>

<style>
body {
  margin: 0;
  background: #f7f7fa;
}
#layout {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  max-width: 960px;
  margin: 0 auto;
  padding: 1rem;
}
nav {
  display: flex;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #ddd;
}
nav a {
  text-decoration: none;
  color: #2b2d42;
  font-weight: 600;
}
.spacer {
  flex: 1;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  text-align: left;
  padding: 0.5rem;
  border-bottom: 1px solid #eee;
}
button {
  cursor: pointer;
}
</style>
