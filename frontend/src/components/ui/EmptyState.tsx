import { Package, Inbox, FileText, Users, Calculator, Settings, Layers, ShoppingCart, BarChart3, Printer } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const icons: Record<string, typeof Package> = {
  jobs: FileText,
  materials: Layers,
  rates: Calculator,
  customers: Users,
  products: Package,
  sales: ShoppingCart,
  reports: BarChart3,
  settings: Settings,
  printers: Printer,
  default: Inbox,
};

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  /**
   * When true, renders a denser inline version suitable for embedded
   * section bodies (side rails, card-body empties). Falls back to the
   * larger centered layout otherwise — use that for full-page empties.
   */
  compact?: boolean;
}

export default function EmptyState({
  icon = 'default',
  title,
  description,
  action,
  className,
  compact = false,
}: EmptyStateProps) {
  const Icon = icons[icon] || icons.default;

  if (compact) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-1 rounded-md border border-dashed border-border bg-card px-4 py-8 text-center',
          className,
        )}
      >
        <Icon className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <p className="mt-2 text-sm font-medium text-foreground">{title}</p>
        {description ? (
          <p className="max-w-xs text-xs text-muted-foreground">{description}</p>
        ) : null}
        {action ? <div className="mt-2">{action}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center px-4 py-16 text-center',
        className,
      )}
    >
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <Icon className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
      </div>
      <h3 className="mb-1 text-lg font-semibold">{title}</h3>
      {description ? (
        <p className="mb-6 max-w-sm text-sm text-muted-foreground">{description}</p>
      ) : null}
      {action}
    </div>
  );
}
