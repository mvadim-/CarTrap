import type { TokenPair, User } from "../types";

const USER_STORAGE_KEY = "cartrap.user";
const TOKEN_STORAGE_KEY = "cartrap.tokens";

export function loadUser(): User | null {
  const raw = localStorage.getItem(USER_STORAGE_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}

export function loadTokens(): TokenPair | null {
  const raw = localStorage.getItem(TOKEN_STORAGE_KEY);
  return raw ? (JSON.parse(raw) as TokenPair) : null;
}

export function saveSession(user: User, tokens: TokenPair): void {
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(tokens));
}

export function clearSession(): void {
  localStorage.removeItem(USER_STORAGE_KEY);
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}
