import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface KPIProps {
  label: string;
  value: string | number;
  delta?: { value: string; positive?: boolean };
  icon?: ReactNode;
  /** Subtle emphasis for attention / success signals. */
  tone?: 'default' | 'warning' | 'success' | 'destructive';
  /** Optional helper text under the value (e.g. "last 7 days"). */
  sub?: string;
}

const toneStyles: Record<NonNullable<KPIProps['tone']>, string> = {
  default: 'text-foreground',
  warning: 'text-amber-600 dark:text-amber-300',
  success: 'text-emerald-600 dark:text-emerald-300',
  destructive: 'text-destructive',
};

export function KPI({ label, value, delta, icon, tone = 'default', sub }: KPIProps) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-border bg-card px-4 py-3 shadow-xs">
      {icon ? <div className="shrink-0 text-muted-foreground">{icon}</div> : null}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className={cn('mt-0.5 text-lg font-semibold tabular-nums', toneStyles[tone])}>{value}</p>
        {sub ? <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p> : null}
      </div>
      {delta ? (
        <span
          className={cn(
            'shrink-0 text-xs font-medium tabular-nums',
            delta.positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'
          )}
        >
          {delta.value}
        </span>
      ) : null}
    </div>
  );
}

interface KPIStripProps {
  children: ReactNode;
  className?: string;
  /** Column layout at >= lg. 2, 3, or 4 columns. Default 4. */
  columns?: 2 | 3 | 4;
}

export function KPIStrip({ children, className, columns = 4 }: KPIStripProps) {
  const colClass =
    columns === 2 ? 'lg:grid-cols-2' : columns === 3 ? 'lg:grid-cols-3' : 'lg:grid-cols-4';
  return <div className={cn('grid gap-3 sm:grid-cols-2', colClass, className)}>{children}</div>;
}
