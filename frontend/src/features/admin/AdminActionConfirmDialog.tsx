import { createPortal } from "react-dom";

import { useBodyScrollLock } from "../shared/useBodyScrollLock";

type Props = {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  isPending: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
};

export function AdminActionConfirmDialog({ isOpen, title, message, confirmLabel, isPending, onClose, onConfirm }: Props) {
  useBodyScrollLock(isOpen);

  if (!isOpen) {
    return null;
  }

  const modal = (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card admin-confirm-dialog" role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <p className="eyebrow">Confirm action</p>
            <h3>{title}</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Cancel
          </button>
        </div>
        <div className="modal-body">
          <p className="muted">{message}</p>
          <div className="admin-confirm-dialog__actions">
            <button type="button" className="ghost-button" onClick={onClose} disabled={isPending}>
              Keep current state
            </button>
            <button type="button" className="danger-button" onClick={() => void onConfirm()} disabled={isPending} aria-busy={isPending}>
              {isPending ? "Working..." : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(modal, document.body) : modal;
}
