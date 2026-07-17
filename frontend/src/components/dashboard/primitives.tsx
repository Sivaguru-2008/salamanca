import React from 'react';
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { formatINRSigned, formatPercentSigned } from '../../lib/currency';

/** Gold eyebrow label used above every panel on the dashboard. */
export const SectionLabel: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <span
    className={`text-[11px] font-bold text-[#c09a5f] uppercase tracking-wider ${className}`}
  >
    {children}
  </span>
);

interface TrendIndicatorProps {
  /** Percentage movement over the period. */
  pct: number;
  /** Absolute movement; shown alongside the percentage when provided. */
  amount?: number;
  /** True where a rise is bad news — debt, expenses. */
  invert?: boolean;
  className?: string;
}

/**
 * Colour-coded movement chip. Growth is green unless `invert` is set, which is
 * how debt going up reads as red while debt going down reads as green.
 */
export const TrendIndicator: React.FC<TrendIndicatorProps> = ({
  pct,
  amount,
  invert = false,
  className = '',
}) => {
  const flat = Math.abs(pct) < 0.05 && (amount === undefined || Math.abs(amount) < 1);
  const rising = pct > 0 || (pct === 0 && (amount ?? 0) > 0);
  const good = invert ? !rising : rising;

  const tone = flat
    ? 'text-brand-graphite/40 bg-black/5'
    : good
      ? 'text-emerald-600 bg-emerald-500/10'
      : 'text-rose-600 bg-rose-500/10';

  const Icon = flat ? Minus : rising ? ArrowUpRight : ArrowDownRight;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums ${tone} ${className}`}
    >
      <Icon size={11} strokeWidth={2.5} />
      {flat ? 'No change' : formatPercentSigned(pct)}
      {amount !== undefined && !flat && (
        <span className="font-semibold opacity-70">{formatINRSigned(amount)}</span>
      )}
    </span>
  );
};

interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  /** Tints the value; used for cash-flow direction. */
  tone?: 'default' | 'positive' | 'negative';
  className?: string;
}

/**
 * Elegant read-only statistic tile. Replaces the grey input-looking boxes the
 * Monthly Overview used to render.
 */
export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  hint,
  tone = 'default',
  className = '',
}) => {
  const valueTone =
    tone === 'positive'
      ? 'text-emerald-600'
      : tone === 'negative'
        ? 'text-rose-600'
        : 'text-brand-navy';

  return (
    <div
      className={`rounded-xl border border-black/5 bg-[#faf8f5] p-4 transition-colors hover:border-[#c09a5f]/30 ${className}`}
    >
      <span className="mb-1.5 block text-[9px] font-bold uppercase tracking-widest text-brand-graphite/40">
        {label}
      </span>
      <span className={`block font-serif text-xl font-semibold tabular-nums ${valueTone}`}>
        {value}
      </span>
      {hint && (
        <span className="mt-1 block text-[10px] text-brand-graphite/45">{hint}</span>
      )}
    </div>
  );
};

/** Full-width empty state shown wherever there is no data to compute from. */
export const EmptyState: React.FC<{ message: string; className?: string }> = ({
  message,
  className = '',
}) => (
  <div
    className={`rounded-xl border border-dashed border-black/10 bg-black/[0.015] px-4 py-8 text-center text-xs text-brand-graphite/50 ${className}`}
  >
    {message}
  </div>
);
