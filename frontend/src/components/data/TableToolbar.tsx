import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface TableToolbarProps {
  /** Left-aligned controls: search, filter selects, etc. */
  children?: ReactNode;
  /** Right-aligned bulk-action or count slot. */
  actions?: ReactNode;
  /** Visible result count (right-aligned, muted). */
  total?: number;
  /** Show a "Clear filters" link when activeFilters > 0. */
  activeFilters?: number;
  onClearFilters?: () => void;
  className?: string;
}

/**
 * Standard toolbar that sits inside the DataTable card, just above the thead.
 * Use it to group search input, status/channel selects, bulk-action button,
 * and the result count into a single row.
 */
export default function TableToolbar({
  children,
  actions,
  total,
  activeFilters = 0,
  onClearFilters,
  className,
}: TableToolbarProps) {
  return (
    <div className={cn('flex flex-wrap items-center gap-2 px-3 py-2', className)}>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
      {activeFilters > 0 && onClearFilters ? (
        <button
          type="button"
          onClick={onClearFilters}
          className="text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          Clear filters ({activeFilters})
        </button>
      ) : null}
      <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
        {typeof total === 'number' ? (
          <span className="tabular-nums">
            {total.toLocaleString()} {total === 1 ? 'result' : 'results'}
          </span>
        ) : null}
        {actions}
      </div>
    </div>
  );
}
