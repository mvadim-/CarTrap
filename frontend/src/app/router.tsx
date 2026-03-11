import { useEffect, useState } from "react";

export type AppRoute = "login" | "invite" | "dashboard";

function parseHash(): { route: AppRoute; params: URLSearchParams } {
  const hash = window.location.hash.replace(/^#/, "") || "/login";
  const [path, query = ""] = hash.split("?");
  const params = new URLSearchParams(query);

  if (path.startsWith("/invite")) {
    return { route: "invite", params };
  }
  if (path.startsWith("/dashboard")) {
    return { route: "dashboard", params };
  }
  return { route: "login", params };
}

export function useHashRoute(): [{ route: AppRoute; params: URLSearchParams }, (nextHash: string) => void] {
  const [state, setState] = useState(parseHash());

  useEffect(() => {
    const onHashChange = () => setState(parseHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function navigate(nextHash: string): void {
    window.location.hash = nextHash;
  }

  return [state, navigate];
}
