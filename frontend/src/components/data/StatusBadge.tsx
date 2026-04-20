import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type StatusTone = 'success' | 'warning' | 'destructive' | 'info' | 'neutral';

const toneStyles: Record<StatusTone, { dot: string; text: string; bg: string }> = {
  success: { dot: 'bg-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', bg: 'bg-emerald-50 dark:bg-emerald-500/10' },
  warning: { dot: 'bg-amber-500', text: 'text-amber-700 dark:text-amber-300', bg: 'bg-amber-50 dark:bg-amber-500/10' },
  destructive: { dot: 'bg-red-500', text: 'text-red-700 dark:text-red-300', bg: 'bg-red-50 dark:bg-red-500/10' },
  info: { dot: 'bg-sky-500', text: 'text-sky-700 dark:text-sky-300', bg: 'bg-sky-50 dark:bg-sky-500/10' },
  neutral: { dot: 'bg-muted-foreground', text: 'text-muted-foreground', bg: 'bg-muted' },
};

/**
 * Map common status strings to visual tones. Any unknown status maps to neutral.
 * Exported so pages can override in one place if the mapping needs tweaking.
 */
export function defaultStatusTone(status: string): StatusTone {
  const s = (status || '').toLowerCase();
  if (['paid', 'delivered', 'complete', 'completed', 'printing', 'active', 'healthy', 'ready', 'ok', 'production'].includes(s)) return 'success';
  if (['pending', 'draft', 'in_progress', 'low_stock', 'queued', 'backorder', 'paused', 'adjustment'].includes(s)) return 'warning';
  if (['refunded', 'cancelled', 'error', 'offline', 'critical', 'failed', 'waste'].includes(s)) return 'destructive';
  if (['shipped', 'maintenance', 'idle', 'scheduled', 'sale', 'return'].includes(s)) return 'info';
  return 'neutral';
}

interface StatusBadgeProps {
  tone?: StatusTone;
  children: ReactNode;
  className?: string;
  /** Hide the leading dot. Useful in very dense grids. */
  hideDot?: boolean;
}

export default function StatusBadge({ tone = 'neutral', children, className, hideDot = false }: StatusBadgeProps) {
  const styles = toneStyles[tone];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 text-xs font-medium',
        styles.bg,
        styles.text,
        className,
      )}
    >
      {!hideDot && <span className={cn('h-1.5 w-1.5 rounded-full', styles.dot)} aria-hidden="true" />}
      {children}
    </span>
  );
}
