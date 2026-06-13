import type { ReactNode } from "react";

export const SIZE_KO: Record<string, string> = { small: "소형", medium: "중형", large: "대형" };
export const TEMPER_KO: Record<string, string> = {
  calm: "차분",
  playful: "활발",
  energetic: "에너지",
  shy: "수줍음",
};

export function dogEmoji(size: string): string {
  return size === "large" ? "🐕" : size === "small" ? "🐩" : "🦮";
}

export function distanceLabel(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${m}m`;
}

export function Verified() {
  return <span className="verified" title="신분·반려동물 등록증 검증 완료">✓ 검증</span>;
}

export function Stars({ value, onChange }: { value: number; onChange?: (n: number) => void }) {
  return (
    <span className="stars">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`star ${n <= value ? "on" : ""}`}
          onClick={() => onChange?.(n)}
          disabled={!onChange}
          aria-label={`${n}점`}
        >
          ★
        </button>
      ))}
    </span>
  );
}

export function Progress({ value }: { value: number }) {
  return (
    <div className="progress">
      <div className="progress-bar" style={{ width: `${Math.max(4, value)}%` }} />
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Banner({ kind, children }: { kind: "ok" | "err" | "info"; children: ReactNode }) {
  return <div className={`banner ${kind}`}>{children}</div>;
}
