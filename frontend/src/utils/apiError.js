/** User-facing copy when the browser / PC has no internet. */
export const NO_NETWORK_MESSAGE =
  'No network connection. Check your internet and try again.';

/**
 * True when the failure looks like offline / unreachable server
 * rather than a normal HTTP error from the API.
 */
export function isNetworkError(error) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return true;
  }
  if (!error) return false;
  const code = String(error.code || '');
  if (code === 'ERR_NETWORK' || code === 'ECONNABORTED' || code === 'ERR_INTERNET_DISCONNECTED') {
    return true;
  }
  const message = String(error.message || '').toLowerCase();
  if (message === 'network error' || message.includes('failed to fetch')) {
    return true;
  }
  // Axios: request was sent but no HTTP response came back.
  if (error.request && !error.response) {
    return true;
  }
  return false;
}

/**
 * Prefer API detail when present; otherwise detect offline and use a clear message.
 */
export function formatApiError(error, fallback = 'Something went wrong.') {
  if (isNetworkError(error)) {
    return NO_NETWORK_MESSAGE;
  }
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message;
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  if (typeof error?.message === 'string' && error.message.trim() && error.message !== 'Network Error') {
    return error.message;
  }
  return fallback;
}
