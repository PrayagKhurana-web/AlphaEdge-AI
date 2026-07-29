"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  getCurrentUser,
  loginUser,
  registerUser,
  type AuthenticatedUser,
} from "@/services/api";
import {
  clearStoredAuthentication,
  readStoredAuthentication,
  saveStoredAuthentication,
} from "@/auth/storage";

export type AuthenticationContextValue = {
  user: AuthenticatedUser | null;
  accessToken: string | null;
  isRestoringSession: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

export const AuthenticationContext =
  createContext<AuthenticationContextValue | null>(null);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isRestoringSession, setIsRestoringSession] = useState(true);

  const clearSession = useCallback(() => {
    clearStoredAuthentication();
    setUser(null);
    setAccessToken(null);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession(): Promise<void> {
      const storedAuthentication = readStoredAuthentication();

      if (!storedAuthentication) {
        if (!cancelled) {
          setIsRestoringSession(false);
        }
        return;
      }

      try {
        const currentUser = await getCurrentUser(
          storedAuthentication.accessToken,
        );

        if (cancelled) {
          return;
        }

        setUser(currentUser);
        setAccessToken(storedAuthentication.accessToken);
      } catch {
        if (!cancelled) {
          clearSession();
        }
      } finally {
        if (!cancelled) {
          setIsRestoringSession(false);
        }
      }
    }

    void restoreSession();

    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  useEffect(() => {
    function handleUnauthorized(): void {
      clearSession();
    }

    window.addEventListener(
      "alphaedge:unauthorized",
      handleUnauthorized,
    );

    return () => {
      window.removeEventListener(
        "alphaedge:unauthorized",
        handleUnauthorized,
      );
    };
  }, [clearSession]);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      const result = await loginUser(email, password);

      saveStoredAuthentication({
        accessToken: result.accessToken,
      });

      setAccessToken(result.accessToken);
      setUser(result.user);
    },
    [],
  );

  const register = useCallback(
    async (email: string, password: string): Promise<void> => {
      const result = await registerUser(email, password);

      saveStoredAuthentication({
        accessToken: result.accessToken,
      });

      setAccessToken(result.accessToken);
      setUser(result.user);
    },
    [],
  );

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const value = useMemo<AuthenticationContextValue>(
    () => ({
      user,
      accessToken,
      isRestoringSession,
      isAuthenticated: user !== null && accessToken !== null,
      login,
      register,
      logout,
    }),
    [
      user,
      accessToken,
      isRestoringSession,
      login,
      register,
      logout,
    ],
  );

  return (
    <AuthenticationContext.Provider value={value}>
      {children}
    </AuthenticationContext.Provider>
  );
}
