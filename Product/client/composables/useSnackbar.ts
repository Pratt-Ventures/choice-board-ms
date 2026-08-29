import type { SnackbarState } from '~/types/api'

const snackbar = ref<SnackbarState>({
  show: false,
  message: '',
  color: 'primary',
})

export function useSnackbar() {
  function show(message: string, color = 'primary') {
    snackbar.value = { show: true, message, color }
  }

  function success(message: string) {
    show(message, 'success')
  }

  function error(message: string) {
    show(message, 'error')
  }

  function info(message: string) {
    show(message, 'info')
  }

  return {
    snackbar,
    show,
    success,
    error,
    info,
  }
}
