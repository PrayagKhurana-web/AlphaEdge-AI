"use client";

import {
  useEffect,
  useState,
  type FormEvent,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/auth/useAuth";
import { AuthenticationApiError } from "@/services/api";

type AuthenticationMode = "login" | "register";

export default function AuthenticationPage() {
  const router = useRouter();
  const {
    login,
    register,
    isAuthenticated,
    isRestoringSession,
  } = useAuth();

  const [mode, setMode] =
    useState<AuthenticationMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");
  const [showPassword, setShowPassword] =
    useState(false);
  const [isSubmitting, setIsSubmitting] =
    useState(false);
  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);

  useEffect(() => {
    if (!isRestoringSession && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [
    isAuthenticated,
    isRestoringSession,
    router,
  ]);

  function changeMode(nextMode: AuthenticationMode): void {
    setMode(nextMode);
    setPassword("");
    setConfirmPassword("");
    setErrorMessage(null);
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);

    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail) {
      setErrorMessage("Enter your email address.");
      return;
    }

    if (password.length < 8) {
      setErrorMessage(
        "Password must contain at least 8 characters.",
      );
      return;
    }

    if (
      mode === "register" &&
      password !== confirmPassword
    ) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      if (mode === "register") {
        await register(normalizedEmail, password);
      } else {
        await login(normalizedEmail, password);
      }

      router.replace("/dashboard");
    } catch (error) {
      if (error instanceof AuthenticationApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(
          "Authentication failed. Make sure the backend is running.",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isRestoringSession) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-black px-6 text-white">
        <p className="text-sm text-zinc-500">
          Checking your session...
        </p>
      </main>
    );
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-black px-6 py-12 text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.12),transparent_45%)]" />

      <div className="relative w-full max-w-md">
        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-zinc-300"
        >
          <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]" />
          AlphaEdge AI
        </Link>

        <section className="rounded-2xl border border-white/10 bg-zinc-950/95 p-6 shadow-2xl sm:p-8">
          <div>
            <p className="text-sm font-medium text-emerald-400">
              {mode === "login"
                ? "Welcome back"
                : "Create your account"}
            </p>

            <h1 className="mt-2 text-2xl font-semibold">
              {mode === "login"
                ? "Log in to AlphaEdge"
                : "Start using AlphaEdge"}
            </h1>

            <p className="mt-2 text-sm leading-relaxed text-zinc-500">
              Your portfolio and watchlist are securely separated
              from every other user.
            </p>
          </div>

          <div className="mt-6 grid grid-cols-2 rounded-xl border border-white/10 bg-black p-1">
            <button
              type="button"
              onClick={() => changeMode("login")}
              className={`rounded-lg px-3 py-2 text-sm transition ${
                mode === "login"
                  ? "bg-zinc-800 text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Login
            </button>

            <button
              type="button"
              onClick={() => changeMode("register")}
              className={`rounded-lg px-3 py-2 text-sm transition ${
                mode === "register"
                  ? "bg-zinc-800 text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              Register
            </button>
          </div>

          <form
            onSubmit={(event) => void handleSubmit(event)}
            className="mt-6 space-y-4"
          >
            <label className="block text-sm text-zinc-300">
              Email address
              <input
                type="email"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                autoComplete="email"
                required
                disabled={isSubmitting}
                placeholder="you@example.com"
                className="mt-2 w-full rounded-xl border border-white/10 bg-black px-3 py-3 text-sm text-white outline-none placeholder:text-zinc-700 focus:border-emerald-400/50 disabled:opacity-60"
              />
            </label>

            <label className="block text-sm text-zinc-300">
              Password
              <div className="relative mt-2">
                <input
                  type={
                    showPassword ? "text" : "password"
                  }
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                  autoComplete={
                    mode === "login"
                      ? "current-password"
                      : "new-password"
                  }
                  required
                  minLength={8}
                  disabled={isSubmitting}
                  placeholder="At least 8 characters"
                  className="w-full rounded-xl border border-white/10 bg-black px-3 py-3 pr-16 text-sm text-white outline-none placeholder:text-zinc-700 focus:border-emerald-400/50 disabled:opacity-60"
                />

                <button
                  type="button"
                  onClick={() =>
                    setShowPassword((current) => !current)
                  }
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-500 hover:text-zinc-300"
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>

            {mode === "register" && (
              <label className="block text-sm text-zinc-300">
                Confirm password
                <input
                  type={
                    showPassword ? "text" : "password"
                  }
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(event.target.value)
                  }
                  autoComplete="new-password"
                  required
                  minLength={8}
                  disabled={isSubmitting}
                  placeholder="Repeat your password"
                  className="mt-2 w-full rounded-xl border border-white/10 bg-black px-3 py-3 text-sm text-white outline-none placeholder:text-zinc-700 focus:border-emerald-400/50 disabled:opacity-60"
                />
              </label>
            )}

            {errorMessage && (
              <div
                aria-live="polite"
                className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300"
              >
                {errorMessage}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-emerald-500 px-4 py-3 text-sm font-semibold text-black transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting
                ? mode === "login"
                  ? "Logging in..."
                  : "Creating account..."
                : mode === "login"
                  ? "Log in"
                  : "Create account"}
            </button>
          </form>

          <p className="mt-5 text-center text-xs leading-relaxed text-zinc-600">
            AlphaEdge provides probability-based analysis and does
            not guarantee investment returns.
          </p>
        </section>
      </div>
    </main>
  );
}
