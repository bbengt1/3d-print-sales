import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type StatusTone = 'success' | 'warning' | 'destructive' | 'info' | 'neutral';

const toneStyles: Record<StatusTone, { dot: string; text: string; surface: string; border: string }> = {
  success: { dot: 'bg-success', text: 'text-success dark:text-success', surface: 'bg-success-surface dark:bg-success/15', border: 'border-success-border dark:border-success/40' },
  warning: { dot: 'bg-warning', text: 'text-warning dark:text-warning', surface: 'bg-warning-surface dark:bg-warning/15', border: 'border-warning-border dark:border-warning/40' },
  destructive: { dot: 'bg-destructive', text: 'text-destructive dark:text-destructive', surface: 'bg-destructive-surface dark:bg-destructive/15', border: 'border-destructive-border dark:border-destructive/40' },
  info: { dot: 'bg-info', text: 'text-info dark:text-info', surface: 'bg-info-surface dark:bg-info/15', border: 'border-info-border dark:border-info/40' },
  neutral: { dot: 'bg-muted-foreground', text: 'text-foreground', surface: 'bg-muted', border: 'border-border' },
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
        'inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-xs font-medium',
        styles.surface,
        styles.border,
        styles.text,
        className,
      )}
    >
      {!hideDot && <span className={cn('h-1.5 w-1.5 rounded-full', styles.dot)} aria-hidden="true" />}
      {children}
    </span>
  );
}
