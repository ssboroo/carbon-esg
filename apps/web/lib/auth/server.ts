import { createNeonAuth } from "@neon/auth/next/server";

const configuredBaseUrl = process.env.NEON_AUTH_BASE_URL;
const configuredCookieSecret = process.env.NEON_AUTH_COOKIE_SECRET;

export const authConfigured = Boolean(
  configuredBaseUrl && configuredCookieSecret && configuredCookieSecret.length >= 32
);

// Keep build-time imports safe; server actions and protected pages check authConfigured
// before using this build-only fallback. Render must provide both real values at runtime.
export const auth = createNeonAuth({
  baseUrl: configuredBaseUrl || "https://missing-neon-auth-configuration.invalid/neondb/auth",
  cookies: {
    secret: configuredCookieSecret || "build-only-placeholder-secret-never-use-in-production"
  }
});
