<template>
  <div class="login">
    <h1>ConnectSphere</h1>
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
  max-width: 320px;
  margin: 4rem auto;
}
form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}
input, textarea {
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.error {
  color: #b00020;
}
</style>
