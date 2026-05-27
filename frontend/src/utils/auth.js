// Shared HTTP Basic credentials for the backend API.
//
// Override with VITE_API_USER / VITE_API_PASS env vars at build time.
// The fallback ("1028@admin") matches the backend's default in main.py so the
// demo works out of the box; production builds without env overrides emit a
// warning so a deploy can't silently ship the demo credentials.

const HAS_OVERRIDE =
  !!import.meta.env.VITE_API_USER && !!import.meta.env.VITE_API_PASS

const API_USER = import.meta.env.VITE_API_USER ?? '1028@admin'
const API_PASS = import.meta.env.VITE_API_PASS ?? '1028@admin'

if (!HAS_OVERRIDE && import.meta.env.PROD) {
  // eslint-disable-next-line no-console
  console.warn(
    '[talk-to-db] Using built-in demo credentials. Set VITE_API_USER and ' +
      'VITE_API_PASS before building for any deployment beyond local demo.',
  )
}

export const AUTH_HEADER = 'Basic ' + btoa(`${API_USER}:${API_PASS}`)
