import type { ReactNode } from "react";

export function Panel({
  title,
  right,
  children,
  pad = true
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  pad?: boolean;
}) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
      {title ? (
        <div className="flex min-h-12 items-center justify-between border-b border-zinc-200 px-4 py-2.5">
          <div className="text-sm font-medium text-zinc-900">{title}</div>
          {right}
        </div>
      ) : null}
      <div className={pad ? "p-4" : ""}>{children}</div>
    </section>
  );
}

export function Button({
  children,
  variant = "secondary",
  onClick,
  type = "button",
  full = false,
  disabled = false
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  onClick?: () => void;
  type?: "button" | "submit";
  full?: boolean;
  disabled?: boolean;
}) {
  const styles = {
    primary: "border-zinc-900 bg-zinc-900 text-white hover:bg-zinc-800",
    secondary: "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50",
    danger: "border-red-300 bg-white text-red-700 hover:bg-red-50",
    ghost: "border-transparent bg-transparent text-zinc-600 hover:bg-zinc-100"
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-md border px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${full ? "w-full" : ""}`}
    >
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = "neutral"
}: {
  children: ReactNode;
  tone?: "neutral" | "healthy" | "warning" | "critical";
}) {
  const styles = {
    neutral: "border-zinc-200 bg-zinc-100 text-zinc-600",
    healthy: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-amber-200 bg-amber-50 text-amber-700",
    critical: "border-red-200 bg-red-50 text-red-700"
  };
  return <span className={`inline-flex rounded-md border px-1.5 py-0.5 text-xs ${styles[tone]}`}>{children}</span>;
}

export function toneForScore(score: number): "healthy" | "warning" | "critical" {
  if (score >= 80) return "healthy";
  if (score >= 55) return "warning";
  return "critical";
}

export function formatBytes(bytes: number) {
  if (bytes >= 1_000_000_000_000) return `${(bytes / 1_000_000_000_000).toFixed(1)} TB`;
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  return `${bytes.toLocaleString()} B`;
}
