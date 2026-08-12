import { API_BASE } from "./apiBase";

export type AuthProviders = {
  google: boolean;
  registration_enabled: boolean;
  registration_allowlist_active: boolean;
};

export async function fetchAuthProviders(): Promise<AuthProviders> {
  const res = await fetch(`${API_BASE}/auth/providers`);
  if (!res.ok) {
    throw new Error("Failed to load auth providers");
  }
  const data = (await res.json()) as Partial<AuthProviders>;
  return {
    google: Boolean(data.google),
    registration_enabled: data.registration_enabled !== false,
    registration_allowlist_active: Boolean(data.registration_allowlist_active),
  };
}
