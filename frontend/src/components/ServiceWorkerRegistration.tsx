"use client";

import { useEffect } from "react";

export default function ServiceWorkerRegistration() {
  useEffect(() => {
    if (
      process.env.NODE_ENV !== "production" ||
      !("serviceWorker" in navigator)
    ) {
      return;
    }

    function registerServiceWorker(): void {
      void navigator.serviceWorker
        .register("/sw.js")
        .catch((error: unknown) => {
          console.error(
            "Service-worker registration failed:",
            error,
          );
        });
    }

    window.addEventListener(
      "load",
      registerServiceWorker,
    );

    return () => {
      window.removeEventListener(
        "load",
        registerServiceWorker,
      );
    };
  }, []);

  return null;
}
