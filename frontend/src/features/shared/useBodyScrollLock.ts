import { useEffect } from "react";

let activeBodyScrollLocks = 0;
let lockedScrollY = 0;
let previousBodyOverflow = "";
let previousBodyPosition = "";
let previousBodyTop = "";
let previousBodyWidth = "";
let previousBodyLeft = "";
let previousBodyRight = "";
let previousHtmlOverflow = "";

export function useBodyScrollLock(isLocked: boolean) {
  useEffect(() => {
    if (!isLocked || typeof document === "undefined" || typeof window === "undefined") {
      return;
    }

    const { body, documentElement } = document;
    if (activeBodyScrollLocks === 0) {
      lockedScrollY = window.scrollY;
      previousBodyOverflow = body.style.overflow;
      previousBodyPosition = body.style.position;
      previousBodyTop = body.style.top;
      previousBodyWidth = body.style.width;
      previousBodyLeft = body.style.left;
      previousBodyRight = body.style.right;
      previousHtmlOverflow = documentElement.style.overflow;

      body.style.overflow = "hidden";
      body.style.position = "fixed";
      body.style.top = `-${lockedScrollY}px`;
      body.style.width = "100%";
      body.style.left = "0";
      body.style.right = "0";
      documentElement.style.overflow = "hidden";
    }

    activeBodyScrollLocks += 1;

    return () => {
      activeBodyScrollLocks = Math.max(0, activeBodyScrollLocks - 1);
      if (activeBodyScrollLocks > 0) {
        return;
      }

      body.style.overflow = previousBodyOverflow;
      body.style.position = previousBodyPosition;
      body.style.top = previousBodyTop;
      body.style.width = previousBodyWidth;
      body.style.left = previousBodyLeft;
      body.style.right = previousBodyRight;
      documentElement.style.overflow = previousHtmlOverflow;

      if (lockedScrollY > 0 && typeof window.scrollTo === "function") {
        try {
          window.scrollTo(0, lockedScrollY);
        } catch {
          // Ignore environments like JSDOM that do not implement scrolling.
        }
      }
    };
  }, [isLocked]);
}
