export const config = {
  apiUrl: import.meta.env.VITE_API_URL || '',
  moyasarPublishableKey: import.meta.env.VITE_MOYASAR_PUBLISHABLE_KEY || '',
} as const;
