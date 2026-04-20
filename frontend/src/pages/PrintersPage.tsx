import { useEffect, useMemo, useState, type ElementType } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Archive,
  ArchiveRestore,
  Camera,
  Edit,
  Expand,
  Layers3,
  PauseCircle,
  Plus,
  Search,
  Sparkles,
  Shrink,
  WifiOff,
  Wrench,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import CameraFeed from '@/components/cameras/CameraFeed';
import PrinterThumbnail from '@/components/printers/PrinterThumbnail';
import EmptyState from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
import PageHeader from '@/components/layout/PageHeader';
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

function SummaryCard({
  label,
  value,
  subtext,
  emphasis = 'default',
}: {
  label: string;
  value: string;
  subtext?: string;
  emphasis?: 'default' | 'warning' | 'success';
}) {
  return (
    <div className="rounded-md border border-border bg-card/80 p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p
        className={cn(
          'mt-3 text-3xl font-semibold',
          emphasis === 'warning' && 'text-amber-600 dark:text-amber-300',
          emphasis === 'success' && 'text-emerald-600 dark:text-emerald-300'
        )}
      >
        {value}
      </p>
      {subtext ? <p className="mt-1 text-sm text-muted-foreground">{subtext}</p> : null}
    </div>
  );
}

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
        'rounded-md border p-4 shadow-md',
        !reducedMotion && 'transition-colors',
        needsAttention
          ? 'border-amber-300/70 bg-amber-50/80 dark:border-amber-500/30 dark:bg-amber-500/10'
          : wallMode
            ? 'border-slate-700/80 bg-slate-950/85 text-slate-50'
            : 'border-border bg-card/85'
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
          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
            {[printer.manufacturer, printer.model, printer.location].filter(Boolean).join(' • ') || 'Printer details pending'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onToggleActive(printer)}
          className={cn(
            'rounded-xl border p-2 transition-colors hover:text-foreground',
            wallMode
              ? 'border-slate-700 bg-slate-900/80 text-slate-300'
              : 'border-border bg-background/70 text-muted-foreground'
          )}
          title={printer.is_active ? 'Deactivate printer' : 'Restore printer'}
        >
          {printer.is_active ? <Archive className="h-4 w-4" /> : <ArchiveRestore className="h-4 w-4" />}
        </button>
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

          <div className={cn('mt-3 h-2 rounded-full', wallMode ? 'bg-slate-900/90' : 'bg-background/90')}>
            <div
              className={cn(
                'h-2 rounded-full',
                !reducedMotion && 'transition-[width]',
                needsAttention ? 'bg-amber-500' : liveStatus === 'printing' ? 'bg-primary' : 'bg-sky-500'
              )}
              style={{ width: `${Math.max(6, progress)}%` }}
            />
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Layer</dt>
              <dd className="font-medium text-foreground">{formatLayer(printer.monitor_current_layer, printer.monitor_total_layers)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">ETA</dt>
              <dd className="font-medium text-foreground">{formatDuration(printer.monitor_remaining_seconds)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Transport</dt>
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
              <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Assignment</dt>
              <dd className="font-medium text-foreground">{currentJob ? currentJob.job_number : 'Unassigned'}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="mt-4 rounded-md border border-border bg-background/60 p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Current job</p>
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
          <Link
            to={`/print-floor/printers/${printer.id}/edit`}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-4 py-2 text-sm font-medium text-foreground no-underline transition-colors hover:border-primary/30"
          >
            <Edit className="h-4 w-4" /> Edit
          </Link>
        ) : null}
        {currentJob ? (
          <Link
            to={`/orders/jobs/${currentJob.id}`}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-4 py-2 text-sm font-medium text-foreground no-underline transition-colors hover:border-primary/30"
          >
            <ArrowRight className="h-4 w-4" /> Job
          </Link>
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
    const printing = activePrinters.filter((printer) => (printer.monitor_status || printer.status) === 'printing').length;
    const attention = activePrinters.filter((printer) => ATTENTION_STATUSES.has(printer.monitor_status || printer.status)).length;
    const ready = activePrinters.filter((printer) => (printer.monitor_status || printer.status) === 'idle').length;
    const unassignedJobs = (activeJobsData?.items || []).filter((job) => !job.printer_id && ACTIVE_ASSIGNMENT_STATUSES.has(job.status)).length;
    const queuePressure = ready === 0 ? activeJobsData?.items.length || 0 : Number(((activeJobsData?.items.length || 0) / ready).toFixed(1));
    const utilization = activePrinters.length ? Math.round((printing / activePrinters.length) * 100) : 0;

    return {
      total: activePrinters.length,
      printing,
      attention,
      ready,
      assigned: activePrinters.filter((printer) => currentJobsByPrinter.has(printer.id)).length,
      unassignedJobs,
      queuePressure,
      utilization,
    };
  }, [currentJobsByPrinter, printers]);

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
        panelTone: 'border-amber-300/70 bg-amber-50/70 dark:border-amber-500/30 dark:bg-amber-500/8',
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
  const analytics = useMemo(() => {
    const activeJobs = activeJobsData?.items || [];
    const printingWithoutTelemetry = printers.filter(
      (printer) => (printer.monitor_status || printer.status) === 'printing' && !printer.monitor_enabled
    ).length;

    return {
      activeJobs: activeJobs.length,
      unassignedJobs: activeJobs.filter((job) => !job.printer_id && ACTIVE_ASSIGNMENT_STATUSES.has(job.status)).length,
      printersAtAttention: attentionPrinters.length,
      printingWithoutTelemetry,
      cameraReadyPlaceholder: printers.filter((printer) => printer.monitor_enabled).length,
    };
  }, [activeJobsData, attentionPrinters.length, printers]);

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

  const updateWallMode = (enabled: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (enabled) {
      next.set('mode', 'wall');
    } else {
      next.delete('mode');
    }
    setSearchParams(next, { replace: true });
  };

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
                <Link
                  to="/orders"
                  className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium no-underline hover:bg-muted transition-colors"
                >
                  <ArrowRight className="h-4 w-4" /> Open jobs queue
                </Link>
              </>
            ) : null}
            <button
              type="button"
              onClick={() => updateWallMode(!wallMode)}
              className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
            >
              {wallMode ? <Shrink className="h-4 w-4" /> : <Expand className="h-4 w-4" />}
              {wallMode ? 'Exit wall mode' : 'Wall mode'}
            </button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <SummaryCard label="Visible active printers" value={String(summary.total)} />
        <SummaryCard label="Printing now" value={String(summary.printing)} emphasis={summary.printing ? 'success' : 'default'} />
        <SummaryCard label="Ready for work" value={String(summary.ready)} emphasis={summary.ready ? 'success' : 'default'} />
        <SummaryCard label="Need attention" value={String(summary.attention)} emphasis={summary.attention ? 'warning' : 'default'} />
        <SummaryCard
          label="Queue pressure"
          value={summary.ready ? `${summary.queuePressure}:1` : `${summary.unassignedJobs}`}
          subtext={summary.ready ? 'Active queue to ready-printer ratio' : 'No ready printers available'}
          emphasis={summary.unassignedJobs > summary.ready ? 'warning' : 'default'}
        />
      </div>

      <div className={cn('grid gap-4', wallMode ? 'xl:grid-cols-3' : 'xl:grid-cols-4')}>
        <SummaryCard
          label="Assignment pressure"
          value={String(analytics.unassignedJobs)}
          subtext="Draft or in-progress jobs missing a printer assignment"
          emphasis={analytics.unassignedJobs ? 'warning' : 'default'}
        />
        <SummaryCard
          label="Telemetry blind spots"
          value={String(analytics.printingWithoutTelemetry)}
          subtext="Printing machines relying on static status or polling only"
          emphasis={analytics.printingWithoutTelemetry ? 'warning' : 'default'}
        />
        <SummaryCard
          label="Urgent floor load"
          value={String(analytics.printersAtAttention + analytics.unassignedJobs)}
          subtext="Attention printers plus queue items needing assignment"
          emphasis={analytics.printersAtAttention + analytics.unassignedJobs ? 'warning' : 'default'}
        />
        <SummaryCard
          label="Live cameras"
          value={String(printers.filter((p) => p.camera_id).length)}
          subtext={`${printers.filter((p) => p.camera_id).length} printers with camera feeds`}
        />
      </div>

      {attentionPrinters.length > 0 ? (
        <section className="rounded-lg border border-amber-300/70 bg-amber-50/80 p-5 shadow-md dark:border-amber-500/30 dark:bg-amber-500/10">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-amber-500" />
                <h2 className="text-lg font-semibold text-foreground">Operator attention strip</h2>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Start here when the floor gets noisy. These are the machines most likely to block work right now.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1 rounded-full bg-background/80 px-3 py-1"><PauseCircle className="h-3.5 w-3.5" /> Paused</span>
              <span className="inline-flex items-center gap-1 rounded-full bg-background/80 px-3 py-1"><WifiOff className="h-3.5 w-3.5" /> Offline</span>
              <span className="inline-flex items-center gap-1 rounded-full bg-background/80 px-3 py-1"><Wrench className="h-3.5 w-3.5" /> Maintenance</span>
              <span className="inline-flex items-center gap-1 rounded-full bg-background/80 px-3 py-1"><AlertTriangle className="h-3.5 w-3.5" /> Error</span>
            </div>
          </div>
        </section>
      ) : null}

      {!wallMode ? (
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_180px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              placeholder="Search printers by name, model, slug, or location..."
              className="w-full rounded-md border border-input bg-card/80 py-3 pl-10 pr-3 focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
            className="rounded-md border border-input bg-card/80 px-3 py-3 focus:outline-none focus:ring-2 focus:ring-ring"
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
            className="rounded-md border border-input bg-card/80 px-3 py-3 focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Active + inactive</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
        </div>
      ) : (
        <section className="rounded-lg border border-slate-700/80 bg-slate-950/80 p-5 shadow-none">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-50">Wall-mode monitor behavior</h2>
              <p className="mt-1 text-sm text-slate-300">
                Reduced chrome, darker surfaces, larger fleet signals, and a 10s refresh interval for persistent shop-floor display.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-300">
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1">
                <Camera className="h-3.5 w-3.5" /> {printers.filter((p) => p.camera_id).length} live camera{printers.filter((p) => p.camera_id).length !== 1 ? 's' : ''}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1">
                {reducedMotion ? 'Reduced motion respected' : 'Motion available'}
              </span>
            </div>
          </div>
        </section>
      )}

      {isLoading || jobsLoading ? (
        <div className={cn('grid gap-4', wallMode ? 'xl:grid-cols-3 2xl:grid-cols-3' : 'xl:grid-cols-3')}>
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="rounded-md border border-border bg-card/85 p-4">
              <div className="mb-4 h-6 w-44 animate-pulse rounded bg-muted" />
              <div className="space-y-3">
                {Array.from({ length: 2 }).map((__, cardIndex) => (
                  <div key={cardIndex} className="h-72 animate-pulse rounded-md border border-border bg-background/70" />
                ))}
              </div>
            </div>
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

            return (
              <section
                key={group.key}
                className={cn('rounded-lg border p-4 shadow-md', group.panelTone || 'border-border bg-card/85')}
              >
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Icon className={cn('h-4 w-4', group.accentClass)} />
                      <h2 className="text-lg font-semibold text-foreground">{group.title}</h2>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{group.description}</p>
                  </div>
                  <span className="rounded-full bg-background/80 px-2.5 py-1 text-xs font-medium text-muted-foreground">
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
                        onToggleActive={toggleActive}
                        wallMode={wallMode}
                        reducedMotion={reducedMotion}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="rounded-md border border-dashed border-border bg-background/60 px-4 py-12 text-center text-sm text-muted-foreground">
                    {group.emptyText}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {totalPages > 1 && !wallMode ? (
        <div className="flex items-center justify-between text-sm">
          <p className="text-muted-foreground">
            Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((current) => Math.max(0, current - 1))}
              disabled={page === 0}
              className="rounded-full border border-border px-4 py-2 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((current) => (current + 1 < totalPages ? current + 1 : current))}
              disabled={page + 1 >= totalPages}
              className="rounded-full border border-border px-4 py-2 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
