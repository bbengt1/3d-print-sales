import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  breadcrumbs?: ReactNode;
  children?: ReactNode;
  className?: string;
}

/**
 * Standard page intro for workspace / list pages. Replaces the decorative
 * dark-gradient hero banners previously used on every page. Keep this
 * compact — the goal is to get to data in <= 120px of vertical space.
 *
 * Usage:
 *   <PageHeader
 *     title="Sales"
 *     description={`${total} total`}
 *     actions={<Link className="...">New sale</Link>}
 *   />
 *
 * With optional KPI strip or tabs below the title:
 *   <PageHeader title="Inventory" description="...">
 *     <KPIStrip>...</KPIStrip>
 *   </PageHeader>
 */
export default function PageHeader({
  title,
  description,
  actions,
  breadcrumbs,
  children,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn('space-y-4', className)}>
      {breadcrumbs}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
          {description ? (
            typeof description === 'string' ? (
              <p className="mt-1 text-sm text-muted-foreground">{description}</p>
            ) : (
              <div className="mt-1 text-sm text-muted-foreground">{description}</div>
            )
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </header>
  );
}
