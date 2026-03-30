import copartLogo from "../../assets/provider-logos/copart.png";
import iaaiLogo from "../../assets/provider-logos/iaai.png";
import type { AuctionProvider } from "../../types";

const PROVIDER_BRANDING: Record<AuctionProvider, { label: string; logoSrc: string }> = {
  copart: {
    label: "Copart",
    logoSrc: copartLogo,
  },
  iaai: {
    label: "IAAI",
    logoSrc: iaaiLogo,
  },
};

export const AUCTION_PROVIDER_OPTIONS = (Object.keys(PROVIDER_BRANDING) as AuctionProvider[]).map((provider) => ({
  value: provider,
  label: PROVIDER_BRANDING[provider].label,
}));

type AuctionProviderBadgeProps = {
  provider: AuctionProvider;
  label?: string | null;
  size?: "compact" | "default";
  tone?: "plain" | "pill";
  showLabel?: boolean;
  className?: string;
};

type AuctionProviderBadgeGroupProps = {
  providers: AuctionProvider[];
  size?: "compact" | "default";
  tone?: "plain" | "pill";
  showLabels?: boolean;
  className?: string;
};

export function getAuctionProviderLabel(provider: AuctionProvider): string {
  return PROVIDER_BRANDING[provider].label;
}

function buildClassName(parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function AuctionProviderBadge({
  provider,
  label = null,
  size = "compact",
  tone = "pill",
  showLabel = true,
  className,
}: AuctionProviderBadgeProps) {
  const branding = PROVIDER_BRANDING[provider];
  const resolvedLabel = label?.trim() || branding.label;

  return (
    <span
      className={buildClassName([
        "auction-provider-badge",
        `auction-provider-badge--${size}`,
        `auction-provider-badge--${tone}`,
        !showLabel && "auction-provider-badge--logo-only",
        className,
      ])}
      aria-label={!showLabel ? resolvedLabel : undefined}
      title={resolvedLabel}
    >
      <span className="auction-provider-badge__logo-frame" aria-hidden="true">
        <img className="auction-provider-badge__logo" src={branding.logoSrc} alt="" />
      </span>
      {showLabel ? <span className="auction-provider-badge__label">{resolvedLabel}</span> : null}
    </span>
  );
}

export function AuctionProviderBadgeGroup({
  providers,
  size = "compact",
  tone = "plain",
  showLabels = false,
  className,
}: AuctionProviderBadgeGroupProps) {
  const uniqueProviders = Array.from(new Set(providers));

  return (
    <div className={buildClassName(["auction-provider-badge-group", className])}>
      {uniqueProviders.map((provider) => (
        <AuctionProviderBadge key={provider} provider={provider} size={size} tone={tone} showLabel={showLabels} />
      ))}
    </div>
  );
}
