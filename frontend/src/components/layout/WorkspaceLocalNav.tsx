import { NavLink, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { getWorkspaceForPath, isWorkspaceLinkActive } from './workspaces';

export default function WorkspaceLocalNav() {
  const location = useLocation();
  const workspace = getWorkspaceForPath(location.pathname);

  return (
    <section className="rounded-lg border border-border bg-card/80 p-4 shadow-md backdrop-blur">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">
            Workspace
          </p>
          <h2 className="mt-1 font-display text-xl font-semibold text-foreground">
            {workspace.label}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {workspace.description}
          </p>
        </div>

        <nav
          aria-label={`${workspace.label} navigation`}
          className="flex flex-wrap gap-2"
        >
          {workspace.localLinks.map((link) => {
            const prefixes = link.matchPrefixes ?? [link.to];
            const active = isWorkspaceLinkActive(location.pathname, prefixes);
            return (
              <NavLink
                key={link.to}
                to={link.to}
                className={cn(
                  'rounded-full border px-3 py-2 text-sm font-medium no-underline transition-colors',
                  active
                    ? 'border-primary/40 bg-primary text-primary-foreground shadow-sm'
                    : 'border-border bg-background/70 text-muted-foreground hover:border-primary/30 hover:text-foreground'
                )}
              >
                {link.label}
              </NavLink>
            );
          })}
        </nav>
      </div>
    </section>
  );
}
