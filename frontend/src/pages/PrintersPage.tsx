import { useEffect, useMemo, useState, type ElementType } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Archive,
  ArchiveRestore,
  Edit,
  Expand,
  Layers3,
  Plus,
  Shrink,
  TriangleAlert,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import CameraFeed from '@/components/cameras/CameraFeed';
import PrinterThumbnail from '@/components/printers/PrinterThumbnail';
import EmptyState from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { Callout, calloutToneClasses } from '@/components/ui/Callout';
import PageHeader from '@/components/layout/PageHeader';
import { KPI, KPIStrip } from '@/components/layout/KPIStrip';
import SearchInput from '@/components/data/SearchInput';
import Pagination from '@/components/data/Pagination';
import { SkeletonCard } from '@/components/ui/Skeleton';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import { cn } from '@/lib/utils';
import type { Job, PaginatedJobs, PaginatedPrinters, Printer } from '@/types';

const STATUS_OPTIONS = ['idle', 'printing', 'paused', 'maintenance', 'offline', 'error'] as const;
const ACTIVE_ASSIGNMENT_STATUSES = new Set(['draft', 'in_progress']);
const ATTENTION_STATUSES = new Set(['paused', 'maintenance', 'offline', 'error']);

function formatDuration(seconds: number | null | undefined) {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatLayer(current: number | null | undefined, total: number | null | undefined) {
  if (current == null && total == null) return '—';
  if (current != null && total != null) return `${current}/${total}`;
  return String(current ?? total ?? '—');
}

type PrinterGroup = {
  key: string;
  title: string;
  description: string;
  emptyText: string;
  icon: ElementType;
  accentClass: string;
  panelTone?: string;
  printers: Printer[];
};

function PrinterWallCard({
  printer,
  currentJob,
  onToggleActive,
  wallMode = false,
  reducedMotion = false,
}: {
  printer: Printer;
  currentJob?: Job;
  onToggleActive: (printer: Printer) => void;
  wallMode?: boolean;
  reducedMotion?: boolean;
}) {
  const liveStatus = printer.monitor_status || printer.status;
  const needsAttention = ATTENTION_STATUSES.has(liveStatus);
  const progress = printer.monitor_progress_percent ?? 0;

  return (
    <article
      className={cn(
        'rounded-md border p-4 shadow-xs',
        !reducedMotion && 'transition-colors',
        needsAttention
          ? calloutToneClasses.warning
          : wallMode
            ? 'border-slate-700/80 bg-slate-950/85 text-slate-50'
            : 'border-border bg-card'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/print-floor/printers/${printer.id}`}
              className="truncate font-semibold text-foreground no-underline hover:text-primary"
            >
              {printer.name}
            </Link>
            <StatusBadge tone={defaultStatusTone(liveStatus)}>
              <span className="capitalize">{liveStatus.replace('_', ' ')}</span>
            </StatusBadge>
            {!printer.is_active ? <StatusBadge tone="warning">Inactive</StatusBadge> : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {[printer.manufacturer, printer.model, printer.location].filter(Boolean).join(' • ') || 'Printer details pending'}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => onToggleActive(printer)}
          title={printer.is_active ? 'Deactivate printer' : 'Restore printer'}
        >
          {printer.is_active ? <Archive className="h-4 w-4" /> : <ArchiveRestore className="h-4 w-4" />}
        </Button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[104px_minmax(0,1fr)]">
        {printer.camera_mse_ws_url || printer.camera_snapshot_url ? (
          <CameraFeed
            mseWsUrl={printer.camera_mse_ws_url}
            snapshotUrl={printer.camera_snapshot_url}
            alt={`${printer.name} camera`}
            className="h-[104px] w-[104px] rounded-md"
            showLiveBadge={false}
          />
        ) : (
        <PrinterThumbnail
          src={printer.current_print_thumbnail_url}
          alt={printer.current_print_name ? `${printer.current_print_name} thumbnail` : `${printer.name} thumbnail`}
          className="h-[104px] w-[104px] rounded-md"
          imgClassName="object-cover"
          fallbackLabel={printer.current_print_name ? 'No thumbnail' : 'No active print'}
        />
        )}

        <div className="min-w-0">
          <div className="flex items-center justify-between gap-3">
            <p className="truncate text-sm font-medium text-foreground">
              {printer.current_print_name || 'No active print'}
            </p>
            <span className="text-sm font-semibold text-foreground">
              {printer.monitor_progress_percent != null ? `${printer.monitor_progress_percent.toFixed(0)}%` : '—'}
            </span>
          </div>

          <div className={cn('mt-3 h-2 rounded-md', wallMode ? 'bg-slate-900/90' : 'bg-background')}>
            <div
              className={cn(
                'h-2 rounded-md',
                !reducedMotion && 'transition-[width]',
                needsAttention ? 'bg-amber-500' : liveStatus === 'printing' ? 'bg-primary' : 'bg-sky-500'
              )}
              style={{ width: `${Math.max(6, progress)}%` }}
            />
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">Layer</dt>
              <dd className="font-medium text-foreground">{formatLayer(printer.monitor_current_layer, printer.monitor_total_layers)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">ETA</dt>
              <dd className="font-medium text-foreground">{formatDuration(printer.monitor_remaining_seconds)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Transport</dt>
              <dd className="font-medium text-foreground">
                {printer.monitor_provider === 'moonraker'
                  ? printer.monitor_ws_connected
                    ? 'Socket live'
                    : 'Polling fallback'
                  : printer.monitor_enabled
                    ? 'Polling'
                    : 'Static record'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Assignment</dt>
              <dd className="font-medium text-foreground">{currentJob ? currentJob.job_number : 'Unassigned'}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className={cn('mt-4 rounded-md border p-3', wallMode ? 'border-slate-700/80 bg-slate-900/60' : 'border-border bg-background')}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Current job</p>
            {currentJob ? (
              <>
                <Link
                  to={`/orders/jobs/${currentJob.id}`}
                  className="mt-1 block truncate font-medium text-primary no-underline hover:underline"
                >
                  {currentJob.job_number}
                </Link>
                <p className="truncate text-sm text-muted-foreground">{currentJob.product_name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{currentJob.total_pieces} pcs • {currentJob.date}</p>
              </>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">No active or draft job is assigned.</p>
            )}
          </div>
          {currentJob ? (
            <StatusBadge tone={defaultStatusTone(currentJob.status)}>
              <span className="capitalize">{currentJob.status.replace('_', ' ')}</span>
            </StatusBadge>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button asChild>
          <Link to={`/print-floor/printers/${printer.id}`}>Open console</Link>
        </Button>
        {!wallMode ? (
          <Button asChild variant="outline" size="sm">
            <Link to={`/print-floor/printers/${printer.id}/edit`}>
              <Edit className="h-4 w-4" /> Edit
            </Link>
          </Button>
        ) : null}
        {currentJob ? (
          <Button asChild variant="outline" size="sm">
            <Link to={`/orders/jobs/${currentJob.id}`}>
              <ArrowRight className="h-4 w-4" /> Job
            </Link>
          </Button>
        ) : null}
      </div>
    </article>
  );
}

export default function PrintersPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [active, setActive] = useState('');
  const [page, setPage] = useState(0);
  const limit = 24;
  const wallMode = searchParams.get('mode') === 'wall';
  const [reducedMotion, setReducedMotion] = useState(false);
  const [pendingToggle, setPendingToggle] = useState<Printer | null>(null);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReducedMotion(media.matches);
    sync();
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, []);

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
    refetchInterval: wallMode ? 10000 : 15000,
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
    const printing = activePrinters.filter((printer) => (printer.monitor_status || printer.status) === 'printing').length;
    const attention = activePrinters.filter((printer) => ATTENTION_STATUSES.has(printer.monitor_status || printer.status)).length;
    const ready = activePrinters.filter((printer) => (printer.monitor_status || printer.status) === 'idle').length;
    const unassignedJobs = (activeJobsData?.items || []).filter((job) => !job.printer_id && ACTIVE_ASSIGNMENT_STATUSES.has(job.status)).length;

    return {
      total: activePrinters.length,
      printing,
      attention,
      ready,
      unassignedJobs,
    };
  }, [activeJobsData, printers]);

  const wallGroups = useMemo<PrinterGroup[]>(() => {
    const activePrinters = printers.filter((printer) => printer.is_active);

    return [
      {
        key: 'attention',
        title: 'Needs attention',
        description: 'Paused, offline, maintenance, or error states that need operator awareness first.',
        emptyText: 'No printers currently need operator attention.',
        icon: AlertTriangle,
        accentClass: 'text-amber-600 dark:text-amber-300',
        panelTone: undefined,
        printers: activePrinters.filter((printer) => ATTENTION_STATUSES.has(printer.monitor_status || printer.status)),
      },
      {
        key: 'printing',
        title: 'Printing now',
        description: 'Machines actively producing parts with live telemetry and current job context.',
        emptyText: 'Nothing is actively printing right now.',
        icon: Activity,
        accentClass: 'text-sky-600 dark:text-sky-300',
        panelTone: 'border-sky-300/70 bg-sky-50/70 dark:border-sky-500/30 dark:bg-sky-500/8',
        printers: activePrinters.filter((printer) => (printer.monitor_status || printer.status) === 'printing'),
      },
      {
        key: 'ready',
        title: 'Ready for work',
        description: 'Idle or unblocked printers that can take the next assignment quickly.',
        emptyText: 'No idle printers in this filtered view.',
        icon: Layers3,
        accentClass: 'text-emerald-600 dark:text-emerald-300',
        panelTone: 'border-emerald-300/70 bg-emerald-50/70 dark:border-emerald-500/30 dark:bg-emerald-500/8',
        printers: activePrinters.filter((printer) => (printer.monitor_status || printer.status) === 'idle'),
      },
    ];
  }, [printers]);

  const attentionPrinters = wallGroups[0]?.printers || [];

  const toggleActive = async (printer: Printer) => {
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

  const updateWallMode = (enabled: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (enabled) {
      next.set('mode', 'wall');
    } else {
      next.delete('mode');
    }
    setSearchParams(next, { replace: true });
  };

  const liveCameras = printers.filter((p) => p.camera_id).length;

  return (
    <div className={cn('space-y-6', wallMode && 'rounded-lg bg-[linear-gradient(180deg,#020617_0%,#08111f_100%)] p-4 text-slate-50')}>
      <PageHeader
        title={wallMode ? 'Print floor — wall mode' : 'Print Floor'}
        description={
          summary.total > 0
            ? `${summary.printing} printing, ${summary.ready} ready${summary.attention ? `, ${summary.attention} need attention` : ''}`
            : 'No printers configured yet'
        }
        actions={
          <>
            {!wallMode ? (
              <>
                <Button asChild>
                  <Link to="/print-floor/printers/new">
                    <Plus className="h-4 w-4" /> Add printer
                  </Link>
                </Button>
                <Button asChild variant="outline">
                  <Link to="/orders">
                    <ArrowRight className="h-4 w-4" /> Open jobs queue
                  </Link>
                </Button>
              </>
            ) : null}
            <Button variant="outline" onClick={() => updateWallMode(!wallMode)}>
              {wallMode ? <Shrink className="h-4 w-4" /> : <Expand className="h-4 w-4" />}
              {wallMode ? 'Exit wall mode' : 'Wall mode'}
            </Button>
          </>
        }
      >
        <KPIStrip columns={4}>
          <KPI
            label="Printing now"
            value={summary.printing}
            tone={summary.printing > 0 ? 'success' : 'default'}
          />
          <KPI
            label="Ready for work"
            value={summary.ready}
            tone={summary.ready > 0 ? 'success' : 'default'}
          />
          <KPI
            label="Need attention"
            value={summary.attention}
            tone={summary.attention > 0 ? 'warning' : 'default'}
          />
          <KPI
            label="Unassigned jobs"
            value={summary.unassignedJobs}
            tone={summary.unassignedJobs > 0 ? 'warning' : 'default'}
            sub="Draft or in-progress without a printer"
            href="/orders/jobs"
          />
        </KPIStrip>
      </PageHeader>

      {attentionPrinters.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          <TriangleAlert className="mr-1 inline h-3.5 w-3.5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
          {attentionPrinters.length} printer{attentionPrinters.length === 1 ? '' : 's'} need attention — start here.
        </p>
      ) : null}

      {wallMode ? (
        <div className="flex flex-wrap gap-3 text-xs text-slate-300">
          <span>{liveCameras} live camera{liveCameras === 1 ? '' : 's'}</span>
          <span>•</span>
          <span>{reducedMotion ? 'Reduced motion respected' : 'Motion available'}</span>
          <span>•</span>
          <span>10s refresh</span>
        </div>
      ) : null}

      {!wallMode ? (
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_180px]">
          <SearchInput
            value={search}
            onChange={(v) => {
              setSearch(v);
              setPage(0);
            }}
            placeholder="Search printers by name, model, slug, or location…"
          />
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option.replace('_', ' ')}
              </option>
            ))}
          </select>
          <select
            value={active}
            onChange={(e) => {
              setActive(e.target.value);
              setPage(0);
            }}
            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Active + inactive</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
        </div>
      ) : null}

      {isLoading || jobsLoading ? (
        <div className="grid gap-4 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} rows={3} />
          ))}
        </div>
      ) : !printers.length ? (
        <EmptyState
          title="No printers found"
          description="Add your first printer to start tracking the print floor, machine status, and assignment context."
          action={
            <Button asChild>
              <Link to="/print-floor/printers/new">
                <Plus className="h-4 w-4" /> Add printer
              </Link>
            </Button>
          }
        />
      ) : (
        <div className={cn('grid gap-4', wallMode ? 'xl:grid-cols-2 2xl:grid-cols-3' : 'xl:grid-cols-3')}>
          {wallGroups.map((group) => {
            const Icon = group.icon;
            const body = (
              <>
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Icon className={cn('h-4 w-4', group.accentClass)} />
                      <h2 className="text-base font-semibold text-foreground">{group.title}</h2>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{group.description}</p>
                  </div>
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {group.printers.length}
                  </span>
                </div>

                {group.printers.length ? (
                  <div className="space-y-3">
                    {group.printers.map((printer) => (
                      <PrinterWallCard
                        key={printer.id}
                        printer={printer}
                        currentJob={currentJobsByPrinter.get(printer.id)}
                        onToggleActive={setPendingToggle}
                        wallMode={wallMode}
                        reducedMotion={reducedMotion}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="rounded-md border border-dashed border-border bg-background px-4 py-12 text-center text-sm text-muted-foreground">
                    {group.emptyText}
                  </div>
                )}
              </>
            );

            if (group.key === 'attention' && group.printers.length > 0) {
              return (
                <Callout key={group.key} tone="warning">
                  <div>{body}</div>
                </Callout>
              );
            }

            const defaultTone = group.key === 'attention' ? undefined : group.panelTone;
            return (
              <section
                key={group.key}
                className={cn('rounded-lg border p-4 shadow-xs', defaultTone || 'border-border bg-card')}
              >
                {body}
              </section>
            );
          })}
        </div>
      )}

      {!wallMode && total > 0 ? (
        <Pagination
          page={page}
          pageSize={limit}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={() => {
            /* no-op; fixed page size */
          }}
        />
      ) : null}

      <ConfirmDialog
        open={pendingToggle !== null}
        onOpenChange={(open) => !open && setPendingToggle(null)}
        title={pendingToggle?.is_active ? 'Deactivate printer?' : 'Restore printer?'}
        description={
          pendingToggle
            ? pendingToggle.is_active
              ? `${pendingToggle.name} will be kept in historical records but removed from active assignment.`
              : `${pendingToggle.name} will be restored to active printers.`
            : undefined
        }
        confirmLabel={pendingToggle?.is_active ? 'Deactivate' : 'Restore'}
        tone={pendingToggle?.is_active ? 'destructive' : 'default'}
        onConfirm={async () => {
          if (pendingToggle) await toggleActive(pendingToggle);
        }}
      />
    </div>
  );
}
