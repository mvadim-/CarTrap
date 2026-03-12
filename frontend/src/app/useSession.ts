import { useState } from "react";

import type { TokenPair, User } from "../types";
import { clearSession, loadTokens, loadUser, saveSession, saveTokens } from "../lib/session";

export function useSession() {
  const [user, setUser] = useState<User | null>(() => loadUser());
  const [tokens, setTokens] = useState<TokenPair | null>(() => loadTokens());

  function persist(nextUser: User, nextTokens: TokenPair) {
    saveSession(nextUser, nextTokens);
    setUser(nextUser);
    setTokens(nextTokens);
  }

  function logout() {
    clearSession();
    setUser(null);
    setTokens(null);
  }

  function updateTokens(nextTokens: TokenPair) {
    saveTokens(nextTokens);
    setTokens(nextTokens);
  }

  return {
    user,
    tokens,
    accessToken: tokens?.access_token ?? null,
    isAuthenticated: Boolean(user && tokens),
    persist,
    updateTokens,
    logout,
  };
}
