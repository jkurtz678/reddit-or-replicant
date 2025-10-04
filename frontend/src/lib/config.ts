import { browser } from '$app/environment';

// API configuration for different environments
export const API_BASE_URL = browser
  ? (import.meta.env.PROD
      ? 'https://redditorreplicant.fly.dev'
      : 'http://localhost:8000')
  : 'http://localhost:8000'; // SSR fallback

export const config = {
  apiUrl: API_BASE_URL,
  isDevelopment: !import.meta.env.PROD,
  isProduction: import.meta.env.PROD
};