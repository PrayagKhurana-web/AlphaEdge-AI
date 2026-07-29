"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/auth/useAuth";

type DashboardAuthGateProps = {
  children: ReactNode;
};

export default function DashboardAuthGate({
  children,
}: DashboardAuthGateProps) {
  const router = useRouter();
  const {
    user,
    isAuthenticated,
    isRestoringSession,
    logout,
  } = useAuth();

  useEffect(() => {
    if (!isRestoringSession && !isAuthenticated) {
      router.replace("/auth");
    }
  }, [
    isAuthenticated,
    isRestoringSession,
    router,
  ]);

  function handleLogout(): void {
    logout();
    router.replace("/auth");
  }

  if (isRestoringSession) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-black px-6 text-white">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-400" />
          <p className="mt-4 text-sm text-zinc-500">
            Restoring your AlphaEdge session...
          </p>
        </div>
      </main>
    );
  }

  if (!isAuthenticated || user === null) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-black px-6 text-white">
        <p className="text-sm text-zinc-500">
          Redirecting to login...
        </p>
      </main>
    );
  }

  return (
    <>
      <div className="border-b border-white/5 bg-zinc-950 px-6 py-3 text-white sm:px-10">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <p className="truncate text-sm text-zinc-400">
            Signed in as{" "}
            <span className="text-zinc-200">
              {user.email}
            </span>
          </p>

          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg border border-white/10 bg-black px-3 py-2 text-xs font-medium text-zinc-300 transition hover:border-red-500/30 hover:text-red-300"
          >
            Log out
          </button>
        </div>
      </div>

      {children}
    </>
  );
}
