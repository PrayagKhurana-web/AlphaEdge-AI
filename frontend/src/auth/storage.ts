export const AUTH_STORAGE_KEY = "alphaedge.auth";

export type StoredAuthentication = {
  accessToken: string;
};

export function readStoredAuthentication():
  | StoredAuthentication
  | null {
  if (typeof window === "undefined") {
    return null;
  }

  const rawValue = window.localStorage.getItem(AUTH_STORAGE_KEY);

  if (!rawValue) {
    return null;
  }

  try {
    const parsedValue = JSON.parse(rawValue) as Partial<StoredAuthentication>;

    if (
      typeof parsedValue.accessToken !== "string" ||
      !parsedValue.accessToken
    ) {
      clearStoredAuthentication();
      return null;
    }

    return {
      accessToken: parsedValue.accessToken,
    };
  } catch {
    clearStoredAuthentication();
    return null;
  }
}

export function getStoredAccessToken(): string | null {
  return readStoredAuthentication()?.accessToken ?? null;
}

export function saveStoredAuthentication(
  authentication: StoredAuthentication,
): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify(authentication),
  );
}

export function clearStoredAuthentication(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function announceUnauthorizedSession(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new Event("alphaedge:unauthorized"));
}
