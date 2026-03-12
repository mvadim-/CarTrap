import { useState } from "react";

type Props = {
  title: string;
  thumbnailUrl: string | null;
  onClick?: () => void;
};

export function LotThumbnail({ title, thumbnailUrl, onClick }: Props) {
  const [hasError, setHasError] = useState(false);

  if (!thumbnailUrl || hasError) {
    return <div className="lot-thumb lot-thumb--placeholder">No image</div>;
  }

  if (!onClick) {
    return <img className="lot-thumb" src={thumbnailUrl} alt={title} onError={() => setHasError(true)} />;
  }

  return (
    <button type="button" className="lot-thumb-button" onClick={onClick} aria-label={`Open gallery for ${title}`}>
      <img className="lot-thumb" src={thumbnailUrl} alt={title} onError={() => setHasError(true)} />
    </button>
  );
}
