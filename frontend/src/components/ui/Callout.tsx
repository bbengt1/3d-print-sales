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
    'border-amber-300/60 bg-amber-50/80 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200',
  success:
    'border-emerald-300/60 bg-emerald-50/80 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200',
  info: 'border-sky-300/60 bg-sky-50/80 text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200',
  danger:
    'border-destructive/40 bg-destructive/10 text-destructive dark:border-destructive/30 dark:bg-destructive/15',
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
 * and info notes. Replaces hand-rolled `bg-amber-50 border-amber-300/60`
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
