import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { shouldUseMobileFullscreen } from "../shared/mobileFullscreen";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";

type Props = {
  title: string;
  imageUrls: string[];
  isOpen: boolean;
  onClose: () => void;
};

export function LotGalleryModal({ title, imageUrls, isOpen, onClose }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const isMobileFullscreen = shouldUseMobileFullscreen();

  useBodyScrollLock(isOpen);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setSelectedIndex(0);

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
      if (event.key === "ArrowRight") {
        setSelectedIndex((current) => Math.min(current + 1, imageUrls.length - 1));
      }
      if (event.key === "ArrowLeft") {
        setSelectedIndex((current) => Math.max(current - 1, 0));
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [imageUrls.length, isOpen, onClose]);

  if (!isOpen || imageUrls.length === 0) {
    return null;
  }

  const modal = (
    <div className={`modal-backdrop${isMobileFullscreen ? " modal-backdrop--mobile-screen" : ""}`} onClick={onClose}>
      <div
        aria-modal="true"
        aria-label={`${title} photo gallery`}
        className={`modal-card gallery-modal${isMobileFullscreen ? " modal-card--mobile-screen gallery-modal--mobile" : ""}`}
        role="dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Gallery</p>
            <h3>{title}</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body gallery-body">
          <img className="gallery-hero" src={imageUrls[selectedIndex]} alt={`${title} photo ${selectedIndex + 1}`} />
          <div className="gallery-strip" role="list" aria-label="Lot photos">
            {imageUrls.map((imageUrl, index) => (
              <button
                key={imageUrl}
                type="button"
                className={`gallery-thumb-button${selectedIndex === index ? " is-active" : ""}`}
                onClick={() => setSelectedIndex(index)}
              >
                <img className="gallery-thumb" src={imageUrl} alt={`${title} thumbnail ${index + 1}`} />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(modal, document.body) : modal;
}
