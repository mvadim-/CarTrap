import type { ProviderConnection } from "../../types";
import { ProviderConnectionCard } from "./ProviderConnectionCard";

type Props = {
  connection: ProviderConnection | null;
  isLoading: boolean;
  loadError: string | null;
  isBrowserOffline: boolean;
  onConnect: (payload: { username: string; password: string }) => Promise<void>;
  onReconnect: (payload: { username: string; password: string }) => Promise<void>;
  onDisconnect: () => Promise<void>;
};

export function CopartConnectionCard({
  connection,
  isLoading,
  loadError,
  isBrowserOffline,
  onConnect,
  onReconnect,
  onDisconnect,
}: Props) {
  return (
    <ProviderConnectionCard
      providerLabel="Copart"
      credentialLabel="Copart email"
      connection={connection}
      isLoading={isLoading}
      loadError={loadError}
      isBrowserOffline={isBrowserOffline}
      onConnect={onConnect}
      onReconnect={onReconnect}
      onDisconnect={onDisconnect}
    />
  );
}
