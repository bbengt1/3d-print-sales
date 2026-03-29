import { useMemo, useState, type ElementType } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus, Search, Eye, Edit, Archive, ArchiveRestore, ArrowRight, Layers3, Activity, PauseCircle, WifiOff, AlertTriangle, Wrench } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import EmptyState from '@/components/ui/EmptyState';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { cn } from '@/lib/utils';
import type { Job, PaginatedJobs, PaginatedPrinters, Printer } from '@/types';

const STATUS_OPTIONS = ['idle', 'printing', 'paused', 'maintenance', 'offline', 'error'] as const;
const ACTIVE_ASSIGNMENT_STATUSES = new Set(['draft', 'in_progress']);
const DEGRADED_STATUSES = new Set(['paused', 'maintenance', 'offline', 'error']);

const statusClasses: Record<string, string> = {
  idle: 'bg-slate-100 text-slate-800 dark:bg-slate-800/60 dark:text-slate-200',
  printing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  paused: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  maintenance: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
  offline: 'bg-zinc-100 text-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-300',
  error: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

const jobStatusClasses: Record<string, string> = {
  completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  in_progress: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  draft: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  cancelled: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
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

function JobStatusBadge({ status }: { status: string }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', jobStatusClasses[status] || 'bg-primary/10 text-primary')}>
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

type PrinterGroup = {
  key: string;
  title: string;
  description: string;
  emptyText: string;
  icon: ElementType;
  accentClass: string;
  printers: Printer[];
};

function PrinterAssignmentCard({ printer, currentJob }: { printer: Printer; currentJob?: Job }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/printers/${printer.id}`} className="font-semibold text-foreground no-underline hover:text-primary">
              {printer.name}
            </Link>
            <StatusBadge status={printer.status} />
            {!printer.is_active && <ActiveBadge isActive={false} />}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {[printer.manufacturer, printer.model].filter(Boolean).join(' · ') || 'Printer details pending'}
            {printer.location ? ` · ${printer.location}` : ''}
          </p>
          {printer.monitor_enabled ? (
            <p className="mt-1 text-xs text-muted-foreground">
              Live: {printer.monitor_status || printer.status}
              {printer.monitor_progress_percent != null ? ` · ${printer.monitor_progress_percent.toFixed(0)}%` : ''}
              {printer.current_print_name ? ` · ${printer.current_print_name}` : ''}
            </p>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">Static record only</p>
          )}
        </div>
        <Link to={`/printers/${printer.id}`} className="rounded-md border border-border p-2 text-muted-foreground hover:bg-accent" title="View printer">
          <Eye className="h-4 w-4" />
        </Link>
      </div>

      <div className="mt-4 rounded-lg border border-border bg-background/40 p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Current assignment</p>
            {currentJob ? (
              <>
                <Link to={`/jobs/${currentJob.id}`} className="mt-1 block font-medium text-primary no-underline hover:underline">
                  {currentJob.job_number}
                </Link>
                <p className="text-sm text-muted-foreground">{currentJob.product_name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{currentJob.total_pieces} pcs · {currentJob.date}</p>
              </>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">No active job assigned.</p>
            )}
          </div>
          {currentJob ? <JobStatusBadge status={currentJob.status} /> : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <Link to={`/printers/${printer.id}`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 no-underline hover:bg-accent">
          <Eye className="h-4 w-4" /> Printer
        </Link>
        <Link to={`/printers/${printer.id}/edit`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 no-underline hover:bg-accent">
          <Edit className="h-4 w-4" /> Edit
        </Link>
        {currentJob ? (
          <Link to={`/jobs/${currentJob.id}`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 no-underline hover:bg-accent">
            <ArrowRight className="h-4 w-4" /> Job
          </Link>
        ) : null}
      </div>
    </div>
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
    refetchInterval: 15000,
  });

  const { data: activeJobsData, isLoading: jobsLoading } = useQuery<PaginatedJobs>({
    queryKey: ['jobs', 'printer-assignments'],
    queryFn: async () => {
      const statuses = ['draft', 'in_progress'];
      const responses = await Promise.all(
        statuses.map((jobStatus) => api.get('/jobs', { params: { status: jobStatus, limit: 100 } }))
      );

      const items = responses
        .flatMap((response) => response.data.items as Job[])
        .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

      return {
        items,
        total: items.length,
        skip: 0,
        limit: items.length,
      } satisfies PaginatedJobs;
    },
  });

  const printers = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  const currentJobsByPrinter = useMemo(() => {
    const assignments = new Map<string, Job>();

    for (const job of activeJobsData?.items || []) {
      if (!job.printer_id || assignments.has(job.printer_id) || !ACTIVE_ASSIGNMENT_STATUSES.has(job.status)) continue;
      assignments.set(job.printer_id, job);
    }

    return assignments;
  }, [activeJobsData]);

  const summary = useMemo(() => {
    const activePrinters = printers.filter((printer) => printer.is_active);

    return {
      total: printers.length,
      idle: activePrinters.filter((printer) => printer.status === 'idle').length,
      printing: activePrinters.filter((printer) => printer.status === 'printing').length,
      attention: activePrinters.filter((printer) => DEGRADED_STATUSES.has(printer.status)).length,
      assigned: activePrinters.filter((printer) => currentJobsByPrinter.has(printer.id)).length,
    };
  }, [currentJobsByPrinter, printers]);

  const dashboardGroups = useMemo<PrinterGroup[]>(() => {
    const activePrinters = printers.filter((printer) => printer.is_active);

    return [
      {
        key: 'idle',
        title: 'Idle printers',
        description: 'Ready for new work with no active print running.',
        emptyText: 'No idle printers in this filtered view.',
        icon: Layers3,
        accentClass: 'text-slate-600 dark:text-slate-300',
        printers: activePrinters.filter((printer) => printer.status === 'idle'),
      },
      {
        key: 'busy',
        title: 'Busy / printing',
        description: 'Machines currently running or marked as printing.',
        emptyText: 'Nothing is actively printing right now.',
        icon: Activity,
        accentClass: 'text-blue-600 dark:text-blue-400',
        printers: activePrinters.filter((printer) => printer.status === 'printing'),
      },
      {
        key: 'attention',
        title: 'Paused / offline / error / maintenance',
        description: 'Printers that need attention before they can take reliable work.',
        emptyText: 'No printers are paused, offline, in error, or under maintenance.',
        icon: AlertTriangle,
        accentClass: 'text-amber-600 dark:text-amber-400',
        printers: activePrinters.filter((printer) => DEGRADED_STATUSES.has(printer.status)),
      },
    ];
  }, [printers]);

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
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Printers</h1>
          <p className="mt-1 text-sm text-muted-foreground">Manage your print farm, machine status, and printer assignments.</p>
        </div>
        <Link to="/printers/new" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground no-underline hover:opacity-90">
          <Plus className="h-4 w-4" /> Add Printer
        </Link>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">Visible printers</p><p className="mt-1 text-2xl font-bold">{summary.total}</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">Idle</p><p className="mt-1 text-2xl font-bold">{summary.idle}</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">Printing</p><p className="mt-1 text-2xl font-bold">{summary.printing}</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">Need attention</p><p className="mt-1 text-2xl font-bold">{summary.attention}</p></div>
        <div className="rounded-lg border border-border bg-card p-4"><p className="text-xs text-muted-foreground">Assigned jobs</p><p className="mt-1 text-2xl font-bold">{summary.assigned}</p></div>
      </div>

      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-5">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Operations dashboard</h2>
            <p className="text-sm text-muted-foreground">Fleet availability and current assignment state from the app-managed printer and job data.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 rounded-full bg-background px-3 py-1"><PauseCircle className="h-3.5 w-3.5" /> Paused</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-background px-3 py-1"><WifiOff className="h-3.5 w-3.5" /> Offline</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-background px-3 py-1"><Wrench className="h-3.5 w-3.5" /> Maintenance</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-background px-3 py-1"><AlertTriangle className="h-3.5 w-3.5" /> Error</span>
          </div>
        </div>

        {isLoading || jobsLoading ? (
          <div className="grid gap-4 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="rounded-lg border border-border bg-background/40 p-4">
                <div className="mb-4 h-6 w-40 animate-pulse rounded bg-muted" />
                <div className="space-y-3">
                  {Array.from({ length: 2 }).map((__, cardIndex) => (
                    <div key={cardIndex} className="h-40 animate-pulse rounded-lg border border-border bg-card" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-3">
            {dashboardGroups.map((group) => {
              const Icon = group.icon;

              return (
                <section key={group.key} className="rounded-lg border border-border bg-background/40 p-4">
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <Icon className={cn('h-4 w-4', group.accentClass)} />
                        <h3 className="font-semibold">{group.title}</h3>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{group.description}</p>
                    </div>
                    <span className="rounded-full bg-card px-2.5 py-1 text-xs font-medium text-muted-foreground">{group.printers.length}</span>
                  </div>

                  {group.printers.length ? (
                    <div className="space-y-3">
                      {group.printers.map((printer) => (
                        <PrinterAssignmentCard key={printer.id} printer={printer} currentJob={currentJobsByPrinter.get(printer.id)} />
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed border-border bg-card/60 px-4 py-10 text-center text-sm text-muted-foreground">
                      {group.emptyText}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </div>

      <div className="mb-6 grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_180px]">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
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
          action={<Link to="/printers/new" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground no-underline hover:opacity-90"><Plus className="h-4 w-4" /> Add Printer</Link>}
        />
      ) : (
        <>
          <div className="hidden overflow-x-auto rounded-lg border border-border bg-card lg:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Manufacturer / Model</th>
                  <th className="px-4 py-3 font-medium">Location</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Live monitor</th>
                  <th className="px-4 py-3 font-medium">Assignment</th>
                  <th className="px-4 py-3 font-medium">State</th>
                  <th className="px-4 py-3 font-medium">Notes</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {printers.map((printer) => {
                  const currentJob = currentJobsByPrinter.get(printer.id);

                  return (
                    <tr key={printer.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                      <td className="px-4 py-3">
                        <div className="font-medium">{printer.name}</div>
                        <div className="font-mono text-xs text-muted-foreground">{printer.slug}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div>{printer.manufacturer || '—'}</div>
                        <div className="text-xs text-muted-foreground">{printer.model || '—'}</div>
                      </td>
                      <td className="px-4 py-3">{printer.location || '—'}</td>
                      <td className="px-4 py-3"><StatusBadge status={printer.status} /></td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {printer.monitor_enabled ? (
                          <div>
                            <div>{printer.monitor_status || printer.status}{printer.monitor_online === false ? ' · offline' : ''}</div>
                            <div>{printer.monitor_progress_percent != null ? `${printer.monitor_progress_percent.toFixed(0)}%` : '—'}{printer.current_print_name ? ` · ${printer.current_print_name}` : ''}</div>
                          </div>
                        ) : (
                          'Not configured'
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {currentJob ? (
                          <div>
                            <Link to={`/jobs/${currentJob.id}`} className="font-medium text-primary no-underline hover:underline">{currentJob.job_number}</Link>
                            <div className="mt-1 text-xs text-muted-foreground">{currentJob.product_name}</div>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">Unassigned</span>
                        )}
                      </td>
                      <td className="px-4 py-3"><ActiveBadge isActive={printer.is_active} /></td>
                      <td className="max-w-xs truncate px-4 py-3 text-muted-foreground">{printer.notes || '—'}</td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1">
                          <Link to={`/printers/${printer.id}`} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent" title="View"><Eye className="h-4 w-4" /></Link>
                          {currentJob ? <Link to={`/jobs/${currentJob.id}`} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent" title="View assigned job"><ArrowRight className="h-4 w-4" /></Link> : null}
                          <Link to={`/printers/${printer.id}/edit`} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent" title="Edit"><Edit className="h-4 w-4" /></Link>
                          <button onClick={() => toggleActive(printer)} className="cursor-pointer rounded-md p-1.5 text-muted-foreground hover:bg-accent" title={printer.is_active ? 'Deactivate printer' : 'Restore printer'}>
                            {printer.is_active ? <Archive className="h-4 w-4" /> : <ArchiveRestore className="h-4 w-4" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="grid gap-3 lg:hidden">
            {printers.map((printer) => {
              const currentJob = currentJobsByPrinter.get(printer.id);

              return (
                <div key={printer.id} className="rounded-lg border border-border bg-card p-4">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div>
                      <Link to={`/printers/${printer.id}`} className="font-semibold text-foreground no-underline hover:text-primary">{printer.name}</Link>
                      <p className="mt-0.5 font-mono text-xs text-muted-foreground">{printer.slug}</p>
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
                      <p className="text-xs text-muted-foreground">Assignment</p>
                      {currentJob ? (
                        <Link to={`/jobs/${currentJob.id}`} className="text-primary no-underline hover:underline">{currentJob.job_number}</Link>
                      ) : (
                        <p>Unassigned</p>
                      )}
                    </div>
                  </div>
                  <div className="mt-3 rounded-lg border border-border bg-background/40 p-3 text-sm">
                    <p className="text-xs text-muted-foreground">Current job</p>
                    {currentJob ? (
                      <>
                        <p className="font-medium">{currentJob.product_name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{currentJob.total_pieces} pcs · {currentJob.date}</p>
                      </>
                    ) : (
                      <p className="text-muted-foreground">No active job assigned.</p>
                    )}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link to={`/printers/${printer.id}`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm no-underline hover:bg-accent">
                      <Eye className="h-4 w-4" /> View
                    </Link>
                    {currentJob ? (
                      <Link to={`/jobs/${currentJob.id}`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm no-underline hover:bg-accent">
                        <ArrowRight className="h-4 w-4" /> Job
                      </Link>
                    ) : null}
                    <Link to={`/printers/${printer.id}/edit`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm no-underline hover:bg-accent">
                      <Edit className="h-4 w-4" /> Edit
                    </Link>
                    <button onClick={() => toggleActive(printer)} className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm hover:bg-accent">
                      {printer.is_active ? <Archive className="h-4 w-4" /> : <ArchiveRestore className="h-4 w-4" />}
                      {printer.is_active ? 'Deactivate' : 'Restore'}
                    </button>
                  </div>
                </div>
              );
            })}
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
