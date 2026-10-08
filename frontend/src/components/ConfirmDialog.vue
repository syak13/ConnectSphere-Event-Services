<template>
    <div v-if="state.visible" class="confirm-overlay">
      <div class="confirm-box">
        <p>{{ state.message }}</p>
        <div class="actions">
          <button class="btn btn-primary" @click="handleConfirm">Confirm</button>
          <button class="btn btn-grey" @click="handleCancel">Cancel</button>
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { useConfirm } from "../composables/useConfirm";
  
  const { state, handleConfirm, handleCancel } = useConfirm();
  </script>
  
  <style scoped>
  .confirm-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
  }
  
  .confirm-box {
    background: #fff;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    max-width: 360px;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  
  .actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
  }
  
  .btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
  }
  
  .btn-primary {
    background: var(--primary, #6a5acd);
    color: #fff;
  }
  
  .btn-grey {
    background: #e2e5ea;
    color: #333;
  }
  </style>