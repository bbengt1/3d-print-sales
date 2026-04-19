import { Fragment, type ReactNode, useMemo } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** Text alignment for the cell content. Default `left`. Numeric columns auto-right-align. */
  align?: 'left' | 'right' | 'center';
  /** Fixed width (e.g. `'120px'` or `'18%'`). Leave undefined for auto. */
  width?: string;
  /** Backend-sortable. When true, clicking the header cycles asc → desc → unsorted. */
  sortable?: boolean;
  /** If the column is numeric, we add `tabular-nums` and right-align by default. */
  numeric?: boolean;
  /** Render the cell content for a given row. */
  cell: (row: T) => ReactNode;
  /** Hide this column below a breakpoint (tailwind class). E.g. `'hidden md:table-cell'`. */
  colClassName?: string;
}

export type SortDir = 'asc' | 'desc';

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;

  /** Row click navigates or opens detail. */
  onRowClick?: (row: T) => void;

  /** Current sort key and direction (controlled). If both set, header shows direction arrow. */
  sortKey?: string;
  sortDir?: SortDir;
  /** Called when a sortable header is clicked. `key=''` + dir ignored means "unsorted". */
  onSortChange?: (key: string, dir: SortDir | null) => void;

  /** Enable row selection with checkbox column. */
  selectable?: boolean;
  selected?: Set<string>;
  onSelectedChange?: (selected: Set<string>) => void;

  /** Skeleton rendering when data is being fetched. */
  loading?: boolean;
  /** Rendered in the tbody when `loading=false` and `data.length === 0`. */
  emptyState?: ReactNode;

  /** Rendered above the tbody, inside the same card. */
  toolbar?: ReactNode;
  /** Rendered below the tbody (typically pagination). */
  footer?: ReactNode;

  /** Freeze thead at top on scroll. Default true. */
  stickyHeader?: boolean;
  /** Row height variant. `compact` = 32px, `normal` = 40px. Default `compact`. */
  density?: 'compact' | 'normal';

  /** Extra class names on the outer card. */
  className?: string;
}

/**
 * Shared business-app data table. Target 32–40px row height, tabular-nums on
 * numeric columns, sticky header, controlled sort + selection state, keyboard
 * navigation, optional toolbar + pagination footer inside the card.
 */
export function DataTable<T>({
  data,
  columns,
  rowKey,
  onRowClick,
  sortKey,
  sortDir,
  onSortChange,
  selectable = false,
  selected,
  onSelectedChange,
  loading = false,
  emptyState,
  toolbar,
  footer,
  stickyHeader = true,
  density = 'compact',
  className,
}: DataTableProps<T>) {
  const rowHeight = density === 'compact' ? 'h-8' : 'h-10';
  const cellPy = density === 'compact' ? 'py-1.5' : 'py-2';

  const allSelected = useMemo(() => {
    if (!selectable || !selected || data.length === 0) return false;
    return data.every((row) => selected.has(rowKey(row)));
  }, [selectable, selected, data, rowKey]);

  const someSelected = useMemo(() => {
    if (!selectable || !selected) return false;
    return data.some((row) => selected.has(rowKey(row))) && !allSelected;
  }, [selectable, selected, data, rowKey, allSelected]);

  const toggleAll = () => {
    if (!onSelectedChange || !selected) return;
    const next = new Set(selected);
    if (allSelected) {
      data.forEach((row) => next.delete(rowKey(row)));
    } else {
      data.forEach((row) => next.add(rowKey(row)));
    }
    onSelectedChange(next);
  };

  const toggleRow = (id: string) => {
    if (!onSelectedChange || !selected) return;
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectedChange(next);
  };

  const handleHeaderClick = (col: Column<T>) => {
    if (!col.sortable || !onSortChange) return;
    if (sortKey !== col.key) {
      onSortChange(col.key, 'asc');
      return;
    }
    if (sortDir === 'asc') {
      onSortChange(col.key, 'desc');
      return;
    }
    // Was desc → go back to unsorted (null key)
    onSortChange('', null);
  };

  const sortIcon = (col: Column<T>) => {
    if (!col.sortable) return null;
    if (sortKey !== col.key) return <ArrowUpDown className="ml-1 inline h-3 w-3 opacity-50" />;
    return sortDir === 'asc' ? (
      <ArrowUp className="ml-1 inline h-3 w-3" />
    ) : (
      <ArrowDown className="ml-1 inline h-3 w-3" />
    );
  };

  return (
    <div className={cn('overflow-hidden rounded-md border border-border bg-card shadow-xs', className)}>
      {toolbar ? <div className="border-b border-border">{toolbar}</div> : null}

      <div className="relative overflow-x-auto">
        <table className="w-full text-sm">
          <thead
            className={cn(
              'border-b border-border bg-card text-xs font-medium uppercase tracking-wide text-muted-foreground',
              stickyHeader && 'sticky top-0 z-10',
            )}
          >
            <tr>
              {selectable ? (
                <th className="w-10 px-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected;
                    }}
                    onChange={toggleAll}
                    aria-label={allSelected ? 'Deselect all rows' : 'Select all rows'}
                    className="h-4 w-4 cursor-pointer rounded border-input accent-primary"
                  />
                </th>
              ) : null}
              {columns.map((col) => {
                const align = col.align || (col.numeric ? 'right' : 'left');
                const isSortable = col.sortable && !!onSortChange;
                return (
                  <th
                    key={col.key}
                    scope="col"
                    style={col.width ? { width: col.width } : undefined}
                    className={cn(
                      'px-3 py-2 text-left font-medium',
                      align === 'right' && 'text-right',
                      align === 'center' && 'text-center',
                      isSortable && 'cursor-pointer select-none hover:text-foreground',
                      col.colClassName,
                    )}
                    onClick={isSortable ? () => handleHeaderClick(col) : undefined}
                    aria-sort={
                      sortKey === col.key
                        ? sortDir === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : isSortable
                          ? 'none'
                          : undefined
                    }
                  >
                    <span className="inline-flex items-center">
                      {col.header}
                      {sortIcon(col)}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={`skeleton-${i}`} className={cn('border-b border-border/60 animate-pulse', rowHeight)}>
                  {selectable ? (
                    <td className="px-3">
                      <div className="h-3 w-3 rounded bg-muted" />
                    </td>
                  ) : null}
                  {columns.map((col) => (
                    <td key={col.key} className={cn('px-3', cellPy)}>
                      <div className="h-3 w-full max-w-[160px] rounded bg-muted" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (selectable ? 1 : 0)}
                  className="px-3 py-12 text-center text-sm text-muted-foreground"
                >
                  {emptyState ?? 'No results.'}
                </td>
              </tr>
            ) : (
              data.map((row) => {
                const id = rowKey(row);
                const isSelected = selectable && selected?.has(id);
                return (
                  <tr
                    key={id}
                    className={cn(
                      'border-b border-border/60 transition-colors',
                      onRowClick && 'cursor-pointer',
                      isSelected ? 'bg-primary/5' : 'hover:bg-muted/60',
                      rowHeight,
                    )}
                    onClick={onRowClick ? (e) => {
                      // Don't trigger rowClick if the click came from the checkbox or an interactive child
                      const target = e.target as HTMLElement;
                      if (target.closest('button, a, input, [role="button"]')) return;
                      onRowClick(row);
                    } : undefined}
                  >
                    {selectable ? (
                      <td className="px-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleRow(id)}
                          aria-label={isSelected ? 'Deselect row' : 'Select row'}
                          className="h-4 w-4 cursor-pointer rounded border-input accent-primary"
                        />
                      </td>
                    ) : null}
                    {columns.map((col) => {
                      const align = col.align || (col.numeric ? 'right' : 'left');
                      return (
                        <td
                          key={col.key}
                          className={cn(
                            'px-3 text-foreground',
                            cellPy,
                            align === 'right' && 'text-right',
                            align === 'center' && 'text-center',
                            col.numeric && 'tabular-nums',
                            col.colClassName,
                          )}
                        >
                          {col.cell(row)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {footer ? <Fragment>{footer}</Fragment> : null}
    </div>
  );
}

export default DataTable;
