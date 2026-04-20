import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer } from 'recharts';
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
  /**
   * Optional drill-through destination. When set, the entire KPI card
   * renders as a react-router `<Link>` so clicking navigates to the
   * underlying list/report with filters pre-applied. An arrow chevron
   * appears on hover to hint at interactivity.
   */
  href?: string;
  /**
   * Optional trend series for an inline sparkline rendered below the
   * value (24px tall). Pass an array of at least 2 numbers. No axes,
   * no tooltip — decorative trend hint only.
   */
  sparkline?: number[];
  /** Override the sparkline stroke color. Default uses the primary token. */
  sparklineColor?: string;
  /** aria-label override when `href` is set. Defaults to `Open {label} details`. */
  linkAriaLabel?: string;
}

const toneStyles: Record<NonNullable<KPIProps['tone']>, string> = {
  default: 'text-foreground',
  warning: 'text-amber-600 dark:text-amber-300',
  success: 'text-emerald-600 dark:text-emerald-300',
  destructive: 'text-destructive',
};

function SparklineLine({ data, color }: { data: number[]; color?: string }) {
  if (!data || data.length < 2) return null;
  const points = data.map((v, i) => ({ i, v }));
  return (
    <div className="mt-1 h-6 w-full" aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={color || 'var(--color-primary)'}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function KPIBody({ label, value, delta, icon, tone = 'default', sub, sparkline, sparklineColor }: KPIProps) {
  return (
    <>
      {icon ? <div className="shrink-0 text-muted-foreground">{icon}</div> : null}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className={cn('mt-0.5 text-lg font-semibold tabular-nums', toneStyles[tone])}>{value}</p>
        {sparkline && sparkline.length >= 2 ? <SparklineLine data={sparkline} color={sparklineColor} /> : null}
        {sub ? <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p> : null}
      </div>
      {delta ? (
        <span
          className={cn(
            'shrink-0 text-xs font-medium tabular-nums',
            delta.positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive',
          )}
        >
          {delta.value}
        </span>
      ) : null}
    </>
  );
}

export function KPI(props: KPIProps) {
  const base =
    'group relative flex items-center gap-3 rounded-md border border-border bg-card px-4 py-3 shadow-xs transition-colors';

  if (props.href) {
    return (
      <Link
        to={props.href}
        aria-label={props.linkAriaLabel || `Open ${props.label} details`}
        className={cn(
          base,
          'no-underline hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        )}
      >
        <KPIBody {...props} />
        <ArrowRight
          aria-hidden="true"
          className="absolute right-2 top-2 h-3.5 w-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
        />
      </Link>
    );
  }

  return (
    <div className={base}>
      <KPIBody {...props} />
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
