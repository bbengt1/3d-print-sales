import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { Fragment, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface BreadcrumbItem {
  label: ReactNode;
  /** Route path. If omitted, the item renders as plain text (usually the current page). */
  to?: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
}

/**
 * Compact breadcrumb trail for detail pages. Place inside `<PageHeader
 * breadcrumbs={<Breadcrumbs items={...} />}>`.
 *
 * The final item is typically the current page — pass it without `to` so
 * it renders as plain muted text.
 */
export default function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  if (!items.length) return null;

  return (
    <nav aria-label="Breadcrumb" className={cn('text-sm', className)}>
      <ol className="flex flex-wrap items-center gap-1 text-muted-foreground">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <Fragment key={`${index}-${String(item.label)}`}>
              <li>
                {item.to && !isLast ? (
                  <Link
                    to={item.to}
                    className="text-muted-foreground no-underline hover:text-foreground hover:underline"
                  >
                    {item.label}
                  </Link>
                ) : (
                  <span className={cn(isLast && 'text-foreground')}>{item.label}</span>
                )}
              </li>
              {!isLast ? (
                <li aria-hidden="true">
                  <ChevronRight className="h-3.5 w-3.5" />
                </li>
              ) : null}
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
