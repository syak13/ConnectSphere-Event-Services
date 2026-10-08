import { reactive } from "vue";

const state = reactive({
  visible: false,
  message: "",
  resolve: null,
});

/**
 * Shared, Promise-based confirmation dialog. Call `confirm(message)` from
 * any component; it returns true/false once the user responds. Backed by
 * one singleton <ConfirmDialog /> mounted once in App.vue.
 */
export function useConfirm() {
  function confirm(message) {
    state.message = message;
    state.visible = true;
    return new Promise((resolve) => {
      state.resolve = resolve;
    });
  }

  function handleConfirm() {
    state.visible = false;
    state.resolve?.(true);
    state.resolve = null;
  }

  function handleCancel() {
    state.visible = false;
    state.resolve?.(false);
    state.resolve = null;
  }

  return { state, confirm, handleConfirm, handleCancel };
}