import type { ReactNode } from "react";

type AsyncStatusTone = "neutral" | "error" | "success";
type AsyncStatusProgress = "none" | "spinner" | "bar";

type Props = {
  title?: string;
  message: ReactNode;
  tone?: AsyncStatusTone;
  progress?: AsyncStatusProgress;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
  live?: "polite" | "assertive";
};

export function AsyncStatus({
  title,
  message,
  tone = "neutral",
  progress = "none",
  action,
  compact = false,
  className = "",
  live = "polite",
}: Props) {
  const classes = [
    "async-status",
    `async-status--${tone}`,
    compact ? "async-status--compact" : "",
    progress === "bar" ? "async-status--bar" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={classes}
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : live}
    >
      {progress === "spinner" ? <span className="async-status__spinner" aria-hidden="true" /> : null}
      {progress === "bar" ? <span className="async-status__bar" aria-hidden="true" /> : null}
      <div className="async-status__content">
        {title ? <strong className="async-status__title">{title}</strong> : null}
        <span className="async-status__message">{message}</span>
      </div>
      {action ? <div className="async-status__action">{action}</div> : null}
    </div>
  );
}
