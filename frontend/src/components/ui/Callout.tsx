import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type CalloutTone = 'warning' | 'success' | 'info' | 'danger' | 'neutral';

/**
 * Shared tone className strings. Pages can import these for card-level
 * warning tints inside iterators (e.g. a PrinterWallCard signalling a
 * needs-attention state) without re-declaring the same amber classes.
 * Prefer the `<Callout>` component for standalone banner/panel surfaces;
 * reach for these constants when the surface must stay a plain card.
 */
export const calloutToneClasses: Record<CalloutTone, string> = {
  warning:
    'border-warning-border bg-warning-surface text-warning dark:border-warning/40 dark:bg-warning/15 dark:text-warning',
  success:
    'border-success-border bg-success-surface text-success dark:border-success/40 dark:bg-success/15 dark:text-success',
  info: 'border-info-border bg-info-surface text-info dark:border-info/40 dark:bg-info/15 dark:text-info',
  danger:
    'border-destructive-border bg-destructive-surface text-destructive dark:border-destructive/40 dark:bg-destructive/15',
  neutral: 'border-border bg-muted text-foreground',
};

const toneStyles = calloutToneClasses;

export interface CalloutProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  tone?: CalloutTone;
  /** Optional leading icon (Lucide). Rendered at `h-4 w-4` before the children. */
  icon?: ReactNode;
  /** Optional title rendered in bold above the body. */
  title?: ReactNode;
}

/**
 * Shared "banner" / "panel" component for inline warnings, confirmations,
 * and info notes. Replaces hand-rolled low-contrast status tints
 * panels. Keep copy short — this is shop-floor chrome, not marketing.
 *
 * Usage:
 * ```tsx
 * <Callout tone="warning" icon={<TriangleAlert className="h-4 w-4" />}
 *          title="Printers need attention">
 *   Two machines are paused. Start from the Print Floor.
 * </Callout>
 * ```
 */
export const Callout = forwardRef<HTMLDivElement, CalloutProps>(function Callout(
  { className, tone = 'warning', icon, title, children, ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      role="status"
      {...props}
      className={cn(
        'rounded-md border p-4 text-sm shadow-xs',
        toneStyles[tone],
        className,
      )}
    >
      <div className="flex items-start gap-2">
        {icon ? <span className="mt-0.5 shrink-0">{icon}</span> : null}
        <div className="min-w-0 flex-1 space-y-1">
          {title ? <p className="font-semibold">{title}</p> : null}
          {children ? <div className={cn(title ? 'text-sm opacity-90' : '')}>{children}</div> : null}
        </div>
      </div>
    </div>
  );
});
