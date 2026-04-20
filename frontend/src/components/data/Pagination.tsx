import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PaginationProps {
  /** 0-based current page index. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (next: number) => void;
  onPageSizeChange?: (next: number) => void;
  pageSizeOptions?: number[];
  className?: string;
}

/**
 * Business-app pagination footer: "Showing N–M of T • Rows per page: X • first/prev/next/last".
 * Always renders even when total is 0 (shows "0 results") to keep the table card footer consistent.
 */
export default function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
  className,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : page * pageSize + 1;
  const end = Math.min((page + 1) * pageSize, total);
  const prevDisabled = page <= 0;
  const nextDisabled = page >= totalPages - 1;

  const btnBase =
    'flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50 disabled:hover:bg-card disabled:hover:text-muted-foreground';

  return (
    <div
      className={cn(
        'flex flex-col gap-3 border-t border-border bg-card px-3 py-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
    >
      <div className="tabular-nums">
        {total === 0 ? 'No results' : (
          <>Showing {start.toLocaleString()}–{end.toLocaleString()} of {total.toLocaleString()}</>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-4">
        {onPageSizeChange ? (
          <label className="flex items-center gap-2">
            <span>Rows per page</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="rounded-md border border-input bg-background px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Rows per page"
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={prevDisabled}
            onClick={() => onPageChange(0)}
            aria-label="First page"
            className={btnBase}
          >
            <ChevronsLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={prevDisabled}
            onClick={() => onPageChange(page - 1)}
            aria-label="Previous page"
            className={btnBase}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="px-2 tabular-nums">
            {page + 1} / {totalPages}
          </span>
          <button
            type="button"
            disabled={nextDisabled}
            onClick={() => onPageChange(page + 1)}
            aria-label="Next page"
            className={btnBase}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={nextDisabled}
            onClick={() => onPageChange(totalPages - 1)}
            aria-label="Last page"
            className={btnBase}
          >
            <ChevronsRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
