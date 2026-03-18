import { useState } from "react";

type Props = {
  title: string;
  thumbnailUrl: string | null;
  onClick?: () => void;
  variant?: "default" | "watchlist";
};

export function LotThumbnail({ title, thumbnailUrl, onClick, variant = "default" }: Props) {
  const [hasError, setHasError] = useState(false);
  const thumbClassName = `lot-thumb${variant === "watchlist" ? " lot-thumb--watchlist" : ""}`;

  if (!thumbnailUrl || hasError) {
    return <div className={`${thumbClassName} lot-thumb--placeholder`}>No image</div>;
  }

  if (!onClick) {
    return <img className={thumbClassName} src={thumbnailUrl} alt={title} onError={() => setHasError(true)} />;
  }

  return (
    <button type="button" className="lot-thumb-button" onClick={onClick} aria-label={`Open gallery for ${title}`}>
      <img className={thumbClassName} src={thumbnailUrl} alt={title} onError={() => setHasError(true)} />
    </button>
  );
}
