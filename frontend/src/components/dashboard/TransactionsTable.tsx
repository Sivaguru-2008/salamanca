import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { apiService } from '../../services/apiService';
import { formatINRPrecise } from '../../lib/currency';
import { Transaction, TransactionPage, TransactionQuery } from '../../types';
import { EmptyState, SectionLabel } from './primitives';

type SortKey = NonNullable<TransactionQuery['sort_by']>;

const PAGE_SIZE = 8;

const STATUS_TONES: Record<string, string> = {
  Completed: 'text-emerald-700 bg-emerald-500/10',
  Pending: 'text-amber-700 bg-amber-500/10',
  Failed: 'text-rose-700 bg-rose-500/10',
};

const isInflow = (tx: Transaction) => tx.type === 'Income' || tx.type === 'Refund';

const SortableHeader: React.FC<{
  label: string;
  column: SortKey;
  active: SortKey;
  dir: 'asc' | 'desc';
  onSort: (column: SortKey) => void;
  className?: string;
}> = ({ label, column, active, dir, onSort, className = '' }) => (
  <th className={`py-2.5 ${className}`}>
    <button
      type="button"
      onClick={() => onSort(column)}
      aria-sort={active === column ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={`inline-flex items-center gap-1 uppercase tracking-wider transition-colors hover:text-[#c09a5f] ${
        active === column ? 'text-[#c09a5f]' : ''
      }`}
    >
      {label}
      {active === column &&
        (dir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
    </button>
  </th>
);

interface TransactionsTableProps {
  /** Bumped by the parent after a write so the ledger refetches. */
  refreshKey?: number;
}

export const TransactionsTable: React.FC<TransactionsTableProps> = ({ refreshKey = 0 }) => {
  const [data, setData] = useState<TransactionPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [sortBy, setSortBy] = useState<SortKey>('transaction_date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Any change to the query resets to the first page, or page 3 of an
  // unfiltered list would survive into a one-page filtered result.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, category, sortBy, sortDir]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiService
      .queryTransactions({
        search: debouncedSearch,
        category,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        page_size: PAGE_SIZE,
      })
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Could not load transactions.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch, category, sortBy, sortDir, page, refreshKey]);

  const onSort = useCallback(
    (column: SortKey) => {
      if (column === sortBy) {
        setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortBy(column);
        setSortDir(column === 'transaction_date' || column === 'amount' ? 'desc' : 'asc');
      }
    },
    [sortBy],
  );

  // The server lists every category the user owns, independent of the active
  // filter, so the options stay complete while a filter is applied.
  const categories = useMemo(() => ['All', ...(data?.categories || [])], [data?.categories]);

  const items = data?.items || [];
  const total = data?.total || 0;
  const totalPages = data?.total_pages || 1;
  const firstRow = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastRow = Math.min(page * PAGE_SIZE, total);
  const isFiltered = Boolean(debouncedSearch) || category !== 'All';

  return (
    <div className="bg-white border border-black/5 rounded-2xl p-6 shadow-premium space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SectionLabel>Recent Transactions</SectionLabel>
        <span className="text-[10px] text-brand-graphite/40 tabular-nums">
          {loading && !data
            ? 'Loading…'
            : total === 0
              ? 'No records'
              : `${firstRow}–${lastRow} of ${total}`}
        </span>
      </div>

      {/* Controls */}
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1 min-w-0">
          <Search
            size={12}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-brand-graphite/40"
          />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search description…"
            aria-label="Search transactions"
            className="w-full min-w-0 rounded-lg border border-transparent bg-black/5 py-2 pl-8 pr-3 text-xs font-medium outline-none transition-colors focus:border-[#c09a5f]/40 focus:bg-white"
          />
        </div>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          aria-label="Filter by category"
          className="min-w-0 rounded-lg border border-transparent bg-black/5 px-3 py-2 text-xs font-semibold outline-none transition-colors focus:border-[#c09a5f]/40 focus:bg-white sm:w-40"
        >
          {categories.map((option) => (
            <option key={option} value={option}>
              {option === 'All' ? 'All categories' : option}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[10px] font-semibold text-amber-800"
        >
          {error}
        </div>
      )}

      {!error && items.length === 0 && !loading ? (
        <EmptyState
          message={
            isFiltered
              ? 'No transactions match these filters.'
              : 'No transactions recorded yet. They will appear here as they are added.'
          }
        />
      ) : (
        <div className="-mx-6 overflow-x-auto px-6">
          <table className="w-full min-w-[680px] text-left text-xs">
            <thead>
              <tr className="border-b border-black/5 font-bold uppercase tracking-wider text-brand-graphite/40">
                <SortableHeader
                  label="Date"
                  column="transaction_date"
                  active={sortBy}
                  dir={sortDir}
                  onSort={onSort}
                />
                <th className="py-2.5">Description</th>
                <SortableHeader
                  label="Category"
                  column="category"
                  active={sortBy}
                  dir={sortDir}
                  onSort={onSort}
                />
                <th className="py-2.5">Type</th>
                <th className="py-2.5">Payment Method</th>
                <SortableHeader
                  label="Amount"
                  column="amount"
                  active={sortBy}
                  dir={sortDir}
                  onSort={onSort}
                  className="text-right"
                />
                <SortableHeader
                  label="Status"
                  column="status"
                  active={sortBy}
                  dir={sortDir}
                  onSort={onSort}
                  className="text-right"
                />
              </tr>
            </thead>
            <tbody
              className={`divide-y divide-black/5 text-brand-graphite/85 transition-opacity ${
                loading ? 'opacity-50' : ''
              }`}
            >
              {items.map((tx) => (
                <tr key={tx.id} className="hover:bg-black/[0.01]">
                  <td className="whitespace-nowrap py-3 tabular-nums">
                    {new Date(tx.transaction_date).toLocaleDateString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </td>
                  <td className="py-3 font-medium">{tx.description || '—'}</td>
                  <td className="py-3">{tx.category}</td>
                  <td className="py-3">
                    <span
                      className={`font-semibold ${
                        isInflow(tx) ? 'text-emerald-600' : 'text-brand-graphite/70'
                      }`}
                    >
                      {isInflow(tx) ? 'Income' : 'Expense'}
                    </span>
                  </td>
                  <td className="whitespace-nowrap py-3 text-brand-graphite/60">
                    {tx.payment_method}
                  </td>
                  <td
                    className={`whitespace-nowrap py-3 text-right font-bold tabular-nums ${
                      isInflow(tx) ? 'text-emerald-600' : 'text-brand-graphite'
                    }`}
                  >
                    {isInflow(tx) ? '+' : '−'}
                    {formatINRPrecise(tx.amount)}
                  </td>
                  <td className="py-3 text-right">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        STATUS_TONES[tx.status] || 'text-brand-graphite/60 bg-black/5'
                      }`}
                    >
                      {tx.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between gap-2 border-t border-black/5 pt-3">
          <span className="text-[10px] font-semibold text-brand-graphite/40 tabular-nums">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-1.5">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              aria-label="Previous page"
              className="flex h-7 w-7 items-center justify-center rounded-full border border-black/5 transition-colors hover:border-[#c09a5f]/40 hover:text-[#c09a5f] disabled:cursor-not-allowed disabled:opacity-30"
            >
              <ChevronLeft size={13} />
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              aria-label="Next page"
              className="flex h-7 w-7 items-center justify-center rounded-full border border-black/5 transition-colors hover:border-[#c09a5f]/40 hover:text-[#c09a5f] disabled:cursor-not-allowed disabled:opacity-30"
            >
              <ChevronRight size={13} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
