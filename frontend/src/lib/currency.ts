/**
 * Indian Rupee formatting for every monetary value in the app.
 *
 * The en-IN locale groups digits in the Indian numbering system
 * (thousand, lakh, crore): 12,500 / 1,25,000 / 12,50,000 / 1,25,00,000.
 */

export const CURRENCY_CODE = 'INR';
export const CURRENCY_SYMBOL = '₹';

const rupees = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: CURRENCY_CODE,
  maximumFractionDigits: 0,
});

const rupeesWithPaise = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: CURRENCY_CODE,
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const safe = (value: unknown): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
};

/** ₹1,25,000 — the default for display. */
export const formatINR = (value: unknown): string => rupees.format(safe(value));

/** ₹1,25,000.50 — only where paise matter, e.g. individual transaction rows. */
export const formatINRPrecise = (value: unknown): string => rupeesWithPaise.format(safe(value));

/** +₹36,500 / -₹4,200 — for deltas and net cash flow, where direction is the point. */
export const formatINRSigned = (value: unknown): string => {
  const num = safe(value);
  return `${num >= 0 ? '+' : '-'}${rupees.format(Math.abs(num))}`;
};

/** 48.7% — one decimal, the convention used across the dashboard. */
export const formatPercent = (value: unknown, digits = 1): string => `${safe(value).toFixed(digits)}%`;

/** +12.4% / -3.1% — signed percentage for trend indicators. */
export const formatPercentSigned = (value: unknown, digits = 1): string => {
  const num = safe(value);
  return `${num >= 0 ? '+' : ''}${num.toFixed(digits)}%`;
};
