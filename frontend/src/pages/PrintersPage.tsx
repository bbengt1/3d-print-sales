import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus, Search, Eye, Edit, Archive, ArchiveRestore } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import EmptyState from '@/components/ui/EmptyState';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { cn } from '@/lib/utils';
import type { PaginatedPrinters, Printer } from '@/types';

const STATUS_OPTIONS = ['idle', 'printing', 'paused', 'maintenance', 'offline', 'error'] as const;

const statusClasses: Record<string, string> = {
  idle: 'bg-slate-100 text-slate-800 dark:bg-slate-800/60 dark:text-slate-200',
  printing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  paused: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  maintenance: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
  offline: 'bg-zinc-100 text-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-300',
  error: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

const activeClasses: Record<string, string> = {
  active: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  inactive: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize', statusClasses[status] || 'bg-primary/10 text-primary')}>
      {status.replace('_', ' ')}
    </span>
  );
}

function ActiveBadge({ isActive }: { isActive: boolean }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', isActive ? activeClasses.active : activeClasses.inactive)}>
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

export default function PrintersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [active, setActive] = useState('');
  const [page, setPage] = useState(0);
  const limit = 24;

  const { data, isLoading } = useQuery<PaginatedPrinters>({
    queryKey: ['printers', { search, status, active, page }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (status) params.set('status', status);
      if (active) params.set('is_active', active);
      params.set('skip', String(page * limit));
      params.set('limit', String(limit));
      const { data } = await api.get(`/printers?${params.toString()}`);
      return data;
    },
  });

  const printers = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  const summary = useMemo(() => ({
    total: printers.length,
    printing: printers.filter((printer) => printer.status === 'printing').length,
    maintenance: printers.filter((printer) => printer.status === 'maintenance').length,
    inactive: printers.filter((printer) => !printer.is_active).length,
  }), [printers]);

  const toggleActive = async (printer: Printer) => {
    const confirmed = window.confirm(
      printer.is_active
        ? `Deactivate ${printer.name}?\n\nThis keeps the printer in historical records but removes it from active assignment.`
        : `Restore ${printer.name} to active printers?`
    );

    if (!confirmed) return;

    try {
      if (printer.is_active) {
        await api.delete(`/printers/${printer.id}`);
        toast.success(`${printer.name} deactivated`);
      } else {
        await api.put(`/printers/${printer.id}`, { is_active: true });
        toast.success(`${printer.name} restored`);
      }
      queryClient.invalidateQueries({ queryKey: ['printers'] });
      queryClient.invalidateQueries({ queryKey: ['printer', printer.id] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update printer');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-3xl font-bold">Printers</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage your print farm, machine status, and printer assignments.</p>
        </div>
        <Link to="/printers/new" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground no-underline hover:opacity-90">
          <Plus className="w-4 h-4" /> Add Printer
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-6">
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">Visible printers</p><p className="text-2xl font-bold mt-1">{summary.total}</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">Currently printing</p><p className="text-2xl font-bold mt-1">{summary.printing}</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">In maintenance</p><p className="text-2xl font-bold mt-1">{summary.maintenance}</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">Inactive</p><p className="text-2xl font-bold mt-1">{summary.inactive}</p></div>
      </div>

      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_180px] mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder="Search printers by name, model, slug, or location..."
            className="w-full rounded-md border border-input bg-background py-2 pr-3 pl-10 focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(0);
          }}
          className="rounded-md border border-input bg-background px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>{option.replace('_', ' ')}</option>
          ))}
        </select>
        <select
          value={active}
          onChange={(e) => {
            setActive(e.target.value);
            setPage(0);
          }}
          className="rounded-md border border-input bg-background px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">Active + inactive</option>
          <option value="true">Active only</option>
          <option value="false">Inactive only</option>
        </select>
      </div>

      {isLoading ? (
        <SkeletonTable rows={6} cols={7} />
      ) : !printers.length ? (
        <EmptyState
          title="No printers found"
          description="Add your first printer to start tracking status, locations, and job assignments."
          action={<Link to="/printers/new" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground no-underline hover:opacity-90"><Plus className="w-4 h-4" /> Add Printer</Link>}
        />
      ) : (
        <>
          <div className="hidden lg:block overflow-x-auto rounded-lg border border-border bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Manufacturer / Model</th>
                  <th className="px-4 py-3 font-medium">Location</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">State</th>
                  <th className="px-4 py-3 font-medium">Notes</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {printers.map((printer) => (
                  <tr key={printer.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                    <td className="px-4 py-3">
                      <div className="font-medium">{printer.name}</div>
                      <div className="text-xs text-muted-foreground font-mono">{printer.slug}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div>{printer.manufacturer || '—'}</div>
                      <div className="text-xs text-muted-foreground">{printer.model || '—'}</div>
                    </td>
                    <td className="px-4 py-3">{printer.location || '—'}</td>
                    <td className="px-4 py-3"><StatusBadge status={printer.status} /></td>
                    <td className="px-4 py-3"><ActiveBadge isActive={printer.is_active} /></td>
                    <td className="px-4 py-3 max-w-xs truncate text-muted-foreground">{printer.notes || '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <Link to={`/printers/${printer.id}`} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent" title="View"><Eye className="w-4 h-4" /></Link>
                        <Link to={`/printers/${printer.id}/edit`} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent" title="Edit"><Edit className="w-4 h-4" /></Link>
                        <button onClick={() => toggleActive(printer)} className="cursor-pointer rounded-md p-1.5 text-muted-foreground hover:bg-accent" title={printer.is_active ? 'Deactivate printer' : 'Restore printer'}>
                          {printer.is_active ? <Archive className="w-4 h-4" /> : <ArchiveRestore className="w-4 h-4" />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid gap-3 lg:hidden">
            {printers.map((printer) => (
              <div key={printer.id} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <Link to={`/printers/${printer.id}`} className="font-semibold text-foreground no-underline hover:text-primary">{printer.name}</Link>
                    <p className="text-xs text-muted-foreground font-mono mt-0.5">{printer.slug}</p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <StatusBadge status={printer.status} />
                    <ActiveBadge isActive={printer.is_active} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Manufacturer</p>
                    <p>{printer.manufacturer || '—'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Model</p>
                    <p>{printer.model || '—'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Location</p>
                    <p>{printer.location || '—'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Notes</p>
                    <p className="line-clamp-2">{printer.notes || '—'}</p>
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <Link to={`/printers/${printer.id}`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm no-underline hover:bg-accent">
                    <Eye className="w-4 h-4" /> View
                  </Link>
                  <Link to={`/printers/${printer.id}/edit`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm no-underline hover:bg-accent">
                    <Edit className="w-4 h-4" /> Edit
                  </Link>
                  <button onClick={() => toggleActive(printer)} className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent">
                    {printer.is_active ? <Archive className="w-4 h-4" /> : <ArchiveRestore className="w-4 h-4" />}
                    {printer.is_active ? 'Deactivate' : 'Restore'}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}</p>
              <div className="flex gap-2">
                <button disabled={page === 0} onClick={() => setPage((current) => current - 1)} className="cursor-pointer rounded-md border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50">Prev</button>
                <span className="px-3 py-1 text-sm">{page + 1} / {totalPages}</span>
                <button disabled={page >= totalPages - 1} onClick={() => setPage((current) => current + 1)} className="cursor-pointer rounded-md border border-border px-3 py-1 text-sm hover:bg-accent disabled:opacity-50">Next</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
