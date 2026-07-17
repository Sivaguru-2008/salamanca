import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, Check, Upload } from 'lucide-react';
import { formatINR } from '../../lib/currency';
import { FinancialData } from '../../types';
import { SectionLabel } from './primitives';

type FieldKey =
  | 'monthly_salary'
  | 'other_monthly_income'
  | 'monthly_expenses'
  | 'current_savings'
  | 'existing_investments'
  | 'current_bank_balance';

interface FieldSpec {
  key: FieldKey;
  label: string;
  /** Salary is the one figure the app cannot compute anything without. */
  required: boolean;
}

const FIELDS: FieldSpec[] = [
  { key: 'monthly_salary', label: 'Monthly Salary (₹)', required: true },
  { key: 'other_monthly_income', label: 'Other Monthly Income (₹)', required: false },
  { key: 'monthly_expenses', label: 'Monthly Expenses (₹)', required: false },
  { key: 'current_savings', label: 'Current Savings (₹)', required: false },
  { key: 'existing_investments', label: 'Existing Investments (₹)', required: false },
  { key: 'current_bank_balance', label: 'Current Bank Balance (₹)', required: false },
];

const MAX_VALUE = 1_000_000_000;

type FormState = Record<FieldKey, string>;
type Errors = Partial<Record<FieldKey, string>>;

const toFormState = (data: FinancialData | null): FormState => ({
  monthly_salary: data?.has_data ? String(data.monthly_salary) : '',
  other_monthly_income: data?.has_data ? String(data.other_monthly_income) : '',
  monthly_expenses: data?.has_data ? String(data.monthly_expenses) : '',
  current_savings: data?.has_data ? String(data.current_savings) : '',
  existing_investments: data?.has_data ? String(data.existing_investments) : '',
  current_bank_balance: data?.has_data ? String(data.current_bank_balance) : '',
});

/** Mirrors the server's rules so the user sees the problem before a round-trip. */
const validateField = (spec: FieldSpec, raw: string): string | undefined => {
  const value = raw.trim();
  if (!value) {
    return spec.required ? `${spec.label.replace(' (₹)', '')} is required.` : 'Enter 0 if none.';
  }
  if (!/^-?\d*\.?\d+$/.test(value)) {
    return 'Enter numbers only.';
  }
  const num = Number(value);
  if (!Number.isFinite(num)) return 'Enter a valid amount.';
  if (num < 0) return 'Cannot be negative.';
  if (spec.required && num <= 0) return 'Must be greater than zero.';
  if (num > MAX_VALUE) return 'That amount looks too large.';
  return undefined;
};

interface FinancialDataFormProps {
  data: FinancialData | null;
  loading: boolean;
  onSubmit: (values: Record<FieldKey, number>) => Promise<void>;
}

export const FinancialDataForm: React.FC<FinancialDataFormProps> = ({
  data,
  loading,
  onSubmit,
}) => {
  const [form, setForm] = useState<FormState>(() => toFormState(data));
  const [errors, setErrors] = useState<Errors>({});
  const [touched, setTouched] = useState<Partial<Record<FieldKey, boolean>>>({});
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [serverError, setServerError] = useState<string | null>(null);

  // Re-seed the inputs once the stored figures arrive, but never stomp on
  // edits the user has already started making.
  const hasEdits = Object.keys(touched).length > 0;
  useEffect(() => {
    if (!hasEdits) setForm(toFormState(data));
  }, [data, hasEdits]);

  const isUpdate = Boolean(data?.has_data);

  const setField = useCallback((key: FieldKey, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setTouched((prev) => ({ ...prev, [key]: true }));
    setStatus('idle');
    setServerError(null);
    const spec = FIELDS.find((f) => f.key === key)!;
    setErrors((prev) => ({ ...prev, [key]: validateField(spec, value) }));
  }, []);

  const validateAll = (): Errors => {
    const next: Errors = {};
    FIELDS.forEach((spec) => {
      const error = validateField(spec, form[spec.key]);
      // Blank optional fields are treated as zero rather than blocking submit.
      if (error && !(!spec.required && !form[spec.key].trim())) next[spec.key] = error;
    });
    return next;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const found = validateAll();
    setErrors(found);
    setTouched(Object.fromEntries(FIELDS.map((f) => [f.key, true])));
    if (Object.keys(found).length > 0) {
      setStatus('error');
      return;
    }

    setStatus('saving');
    setServerError(null);
    try {
      await onSubmit(
        Object.fromEntries(
          FIELDS.map((f) => [f.key, Number(form[f.key].trim() || 0)]),
        ) as Record<FieldKey, number>,
      );
      setStatus('saved');
      setTouched({});
      setTimeout(() => setStatus('idle'), 2500);
    } catch (error) {
      setStatus('error');
      setServerError(error instanceof Error ? error.message : 'Could not save your data.');
    }
  };

  const preview = useMemo(
    () =>
      FIELDS.map((spec) => ({
        label: spec.label.replace(' (₹)', ''),
        value: data ? formatINR(data[spec.key]) : formatINR(0),
      })),
    [data],
  );

  return (
    <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-5">
      <div className="flex items-center justify-between gap-2">
        <SectionLabel>Financial Data</SectionLabel>
        {isUpdate && data?.updated_at && (
          <span className="text-[9px] text-brand-graphite/40">
            Updated {new Date(data.updated_at).toLocaleDateString('en-IN')}
          </span>
        )}
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-3.5">
          {FIELDS.map((spec) => {
            const error = touched[spec.key] ? errors[spec.key] : undefined;
            return (
              <div key={spec.key} className="flex flex-col gap-1.5">
                <label
                  htmlFor={spec.key}
                  className="text-[10px] font-bold text-brand-graphite/40 uppercase tracking-wider"
                >
                  {spec.label}
                  {spec.required && <span className="text-[#c09a5f]"> *</span>}
                </label>
                <input
                  id={spec.key}
                  name={spec.key}
                  type="text"
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="0"
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? `${spec.key}-error` : undefined}
                  className={`w-full min-w-0 rounded-lg border bg-black/5 px-3 py-2 text-xs font-semibold tabular-nums outline-none transition-colors focus:bg-white ${
                    error
                      ? 'border-rose-400/60 focus:border-rose-500'
                      : 'border-transparent focus:border-[#c09a5f]/40'
                  }`}
                  value={form[spec.key]}
                  onChange={(e) => setField(spec.key, e.target.value)}
                  onBlur={() => setTouched((prev) => ({ ...prev, [spec.key]: true }))}
                />
                {error && (
                  <span
                    id={`${spec.key}-error`}
                    role="alert"
                    className="flex items-center gap-1 text-[10px] font-semibold text-rose-600"
                  >
                    <AlertCircle size={11} />
                    {error}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {serverError && (
          <div
            role="alert"
            className="flex items-start gap-1.5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[10px] font-semibold text-rose-700"
          >
            <AlertCircle size={12} className="mt-px shrink-0" />
            {serverError}
          </div>
        )}

        <button
          type="submit"
          disabled={status === 'saving' || loading}
          className="flex w-full items-center justify-center gap-1.5 rounded-full bg-brand-navy py-2.5 text-xs font-semibold text-white shadow-subtle transition-colors hover:bg-[#c09a5f] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {status === 'saved' ? (
            <>
              <Check size={13} /> Saved
            </>
          ) : (
            <>
              <Upload size={13} />
              {status === 'saving'
                ? 'Saving…'
                : isUpdate
                  ? 'Update Data'
                  : 'Upload Financial Data'}
            </>
          )}
        </button>
      </form>

      {/* The stored figures, echoed back so a submit visibly took effect. */}
      {isUpdate && (
        <div className="space-y-2 border-t border-black/5 pt-4">
          <span className="block text-[9px] font-bold uppercase tracking-widest text-brand-graphite/40">
            Your Saved Data
          </span>
          <dl className="space-y-1.5">
            {preview.map((row) => (
              <div key={row.label} className="flex items-baseline justify-between gap-3">
                <dt className="text-[11px] text-brand-graphite/60">{row.label}</dt>
                <dd className="font-serif text-xs font-semibold tabular-nums text-brand-navy">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
};
