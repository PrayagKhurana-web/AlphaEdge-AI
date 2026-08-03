"use client";

import { useContext } from "react";

import {
  AuthenticationContext,
  type AuthenticationContextValue,
} from "@/auth/AuthProvider";

export function useAuth(): AuthenticationContextValue {
  const context = useContext(AuthenticationContext);

  if (context === null) {
    throw new Error(
      "useAuth must be used inside the AuthProvider.",
    );
  }

  return context;
}
