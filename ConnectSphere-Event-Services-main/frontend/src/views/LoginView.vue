<template>
  <div class="login">
    <div class="card">
      <h1>ConnectSphere</h1>
      <p class="subtitle">Log in to continue</p>
      <form @submit.prevent="handleSubmit">
        <label>
          Email
          <input v-model="email" type="email" required />
        </label>
        <label>
          Password
          <input v-model="password" type="password" required />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit">Log in</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const email = ref("");
const password = ref("");
const error = ref("");
const auth = useAuthStore();
const router = useRouter();

async function handleSubmit() {
  error.value = "";
  try {
    await auth.login(email.value, password.value);
    router.push({ name: "dashboard" });
  } catch (e) {
    error.value = e.response?.data?.error || "Login failed";
  }
}
</script>

<style scoped>
.login {
  max-width: 380px;
  margin: 3rem auto;
}

.card {
  padding: 2rem 1.75rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #e4defa);
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(109, 91, 208, 0.12);
}

h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
  text-align: center;
  color: var(--primary, #6d5bd0);
}

.subtitle {
  margin: 0.35rem 0 1.5rem;
  text-align: center;
  color: var(--text-muted, #6b6890);
}

form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text, #2d2a4a);
}

input {
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border, #e4defa);
  border-radius: 10px;
  background: #fcfbff;
  color: var(--text, #2d2a4a);
  font: inherit;
  font-weight: 400;
}

input:focus {
  outline: none;
  border-color: var(--primary, #6d5bd0);
  background: #ffffff;
  box-shadow: 0 0 0 3px var(--primary-tint, #ebe7ff);
}

button {
  margin-top: 0.25rem;
  padding: 0.7rem 1rem;
  border: none;
  border-radius: 999px;
  background: var(--primary, #6d5bd0);
  color: #ffffff;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

button:hover {
  background: var(--primary-hover, #5b49bd);
}

button:focus-visible {
  outline: 2px solid var(--primary, #6d5bd0);
  outline-offset: 2px;
}

.error {
  margin: 0;
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
  background: var(--rose-bg, #ffdce3);
  color: var(--rose-text, #a12b47);
  font-size: 0.9rem;
}
</style>