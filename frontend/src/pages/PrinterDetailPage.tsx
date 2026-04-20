import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowLeft,
  Archive,
  ArchiveRestore,
  Edit,
  Expand,
  Gauge,
  Layers3,
  PlugZap,
  RefreshCw,
  Thermometer,
  Timer,
} from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { cn, formatCurrency } from '@/lib/utils';
import { getApiErrorMessage } from '@/lib/apiError';
import CameraFeed from '@/components/cameras/CameraFeed';
import PrinterThumbnail from '@/components/printers/PrinterThumbnail';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import PageHeader from '@/components/layout/PageHeader';
import Breadcrumbs from '@/components/ui/Breadcrumbs';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import type { Job, PaginatedJobs, Printer, PrinterConnectionTestResult } from '@/types';

function formatDateTime(value: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

function formatDuration(seconds: number | null | undefined) {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatTemperature(actual: number | null | undefined, target: number | null | undefined) {
  if (actual == null && target == null) return '—';
  if (actual != null && target != null) return `${actual.toFixed(1)} / ${target.toFixed(1)} C`;
  if (actual != null) return `${actual.toFixed(1)} C`;
  return `Target ${target?.toFixed(1)} C`;
}

function formatLayer(current: number | null | undefined, total: number | null | undefined) {
  if (current == null && total == null) return '—';
  if (current != null && total != null) return `${current} / ${total}`;
  return String(current ?? total ?? '—');
}

function formatEventMetaValue(value: unknown) {
  if (value == null || value === '') return null;
  return String(value);
}

function ConsoleStat({
  icon: Icon,
  label,
  value,
  subtext,
  emphasis = 'default',
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  subtext?: string;
  emphasis?: 'default' | 'warning' | 'success';
}) {
  return (
    <div className="rounded-md border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p
            className={cn(
              'mt-3 text-2xl font-semibold',
              emphasis === 'warning' && 'text-amber-600 dark:text-amber-300',
              emphasis === 'success' && 'text-emerald-600 dark:text-emerald-300'
            )}
          >
            {value}
          </p>
          {subtext ? <p className="mt-1 text-sm text-muted-foreground">{subtext}</p> : null}
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary/12 text-primary">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export default function PrinterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: printer, isLoading: printerLoading } = useQuery<Printer>({
    queryKey: ['printer', id],
    queryFn: () => api.get(`/printers/${id}`).then((response) => response.data),
    enabled: Boolean(id),
    refetchInterval: (query) =>
      query.state.data?.monitor_enabled
        ? Math.max((query.state.data.monitor_poll_interval_seconds || 30) * 1000, 5000)
        : false,
  });

  const { data: jobs, isLoading: jobsLoading } = useQuery<PaginatedJobs>({
    queryKey: ['printer-jobs', id],
    queryFn: () => api.get('/jobs', { params: { printer_id: id, limit: 10 } }).then((response) => response.data),
    enabled: Boolean(id),
  });

  const [confirmToggle, setConfirmToggle] = useState(false);

  const toggleActive = async () => {
    if (!printer) return;
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
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to update printer'));
    }
  };

  const refreshNow = async () => {
    if (!printer) return;
    try {
      await api.post(`/printers/${printer.id}/refresh`);
      toast.success('Live status refreshed');
      queryClient.invalidateQueries({ queryKey: ['printer', printer.id] });
      queryClient.invalidateQueries({ queryKey: ['printers'] });
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Refresh failed'));
    }
  };

  const testConnection = async () => {
    if (!printer) return;
    try {
      const { data } = await api.post<PrinterConnectionTestResult>(`/printers/${printer.id}/test-connection`);
      data.ok ? toast.success(data.message || 'Connection successful') : toast.error(data.message || 'Connection failed');
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Connection test failed'));
    }
  };

  if (printerLoading) return <SkeletonTable rows={5} cols={4} />;
  if (!printer) return <p className="py-16 text-center text-muted-foreground">Printer not found</p>;

  const recentJobs = jobs?.items || [];
  const activeJob = recentJobs.find((job) => job.status === 'in_progress' || job.status === 'draft');
  const liveStatus = printer.monitor_status || printer.status;
  const progress = printer.monitor_progress_percent ?? 0;
  const needsAttention = ['paused', 'maintenance', 'offline', 'error'].includes(liveStatus);

  return (
    <div className="space-y-6">
      <Link
        to="/print-floor"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground no-underline transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to printer wall
      </Link>

      <PageHeader
        title={printer.name}
        breadcrumbs={
          <Breadcrumbs
            items={[
              { to: '/print-floor', label: 'Print Floor' },
              { label: printer.name },
            ]}
          />
        }
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={defaultStatusTone(liveStatus)}>
              <span className="capitalize">{liveStatus.replace('_', ' ')}</span>
            </StatusBadge>
            <StatusBadge tone={printer.is_active ? 'success' : 'warning'}>
              {printer.is_active ? 'Active' : 'Inactive'}
            </StatusBadge>
            <span className="text-muted-foreground">
              {[printer.manufacturer, printer.model, printer.location].filter(Boolean).join(' • ') || printer.slug}
            </span>
          </span>
        }
        actions={
          <>
            {printer.monitor_enabled ? (
              <>
                <Button onClick={testConnection}>
                  <PlugZap className="h-4 w-4" /> Test connection
                </Button>
                <Button variant="outline" onClick={refreshNow}>
                  <RefreshCw className="h-4 w-4" /> Refresh
                </Button>
              </>
            ) : null}
            <Button asChild variant="outline">
              <Link to={`/print-floor/printers/${printer.id}/edit`}>
                <Edit className="h-4 w-4" /> Edit
              </Link>
            </Button>
            <Button variant="outline" onClick={() => setConfirmToggle(true)}>
              {printer.is_active ? <Archive className="h-4 w-4" /> : <ArchiveRestore className="h-4 w-4" />}
              {printer.is_active ? 'Deactivate' : 'Restore'}
            </Button>
          </>
        }
      >
        <div className="rounded-md border border-border bg-card p-5 shadow-xs">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-muted-foreground">Current print</p>
              <p className="mt-1 text-base font-semibold text-foreground">{printer.current_print_name || 'No active print'}</p>
            </div>
            <span className="text-2xl font-semibold tabular-nums">
              {printer.monitor_progress_percent != null ? `${printer.monitor_progress_percent.toFixed(0)}%` : '—'}
            </span>
          </div>

          <div className="mt-4 h-2 rounded-full bg-muted">
            <div
              className={cn('h-2 rounded-full transition-[width]', needsAttention ? 'bg-amber-500' : 'bg-primary')}
              style={{ width: `${Math.max(6, progress)}%` }}
            />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <p className="text-xs text-muted-foreground">Layer</p>
              <p className="mt-1 font-medium tabular-nums">{formatLayer(printer.monitor_current_layer, printer.monitor_total_layers)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">ETA</p>
              <p className="mt-1 font-medium tabular-nums">{formatDuration(printer.monitor_remaining_seconds)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Transport</p>
              <p className="mt-1 font-medium">
                {printer.monitor_provider === 'moonraker'
                  ? printer.monitor_ws_connected
                    ? 'Socket live'
                    : 'Polling fallback'
                  : printer.monitor_enabled
                    ? 'Polling'
                    : 'Static record'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Assignment</p>
              <p className="mt-1 font-medium">{activeJob ? activeJob.job_number : 'Unassigned'}</p>
            </div>
          </div>
        </div>
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ConsoleStat
          icon={Gauge}
          label="Progress"
          value={printer.monitor_progress_percent != null ? `${printer.monitor_progress_percent.toFixed(1)}%` : '—'}
          subtext={printer.current_print_name || 'No active file'}
          emphasis={printer.monitor_progress_percent ? 'success' : 'default'}
        />
        <ConsoleStat
          icon={Timer}
          label="Elapsed / remaining"
          value={`${formatDuration(printer.monitor_elapsed_seconds)} / ${formatDuration(printer.monitor_remaining_seconds)}`}
          subtext={printer.monitor_eta_at ? `ETA ${formatDateTime(printer.monitor_eta_at)}` : 'ETA unavailable'}
        />
        <ConsoleStat
          icon={Thermometer}
          label="Tool temperature"
          value={formatTemperature(printer.monitor_tool_temp_c, printer.monitor_tool_target_c)}
          subtext={`Bed ${formatTemperature(printer.monitor_bed_temp_c, printer.monitor_bed_target_c)}`}
        />
        <ConsoleStat
          icon={Layers3}
          label="Assignment"
          value={activeJob ? activeJob.job_number : 'Unassigned'}
          subtext={activeJob ? `${activeJob.total_pieces} pcs • ${activeJob.product_name}` : 'No draft or in-progress job attached'}
          emphasis={activeJob ? 'success' : needsAttention ? 'warning' : 'default'}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <section className="rounded-md border border-border bg-card p-5 shadow-xs">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-foreground">Live monitoring</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                A denser, operator-friendly view of the current telemetry from the configured monitoring provider.
              </p>
            </div>
            {printer.monitor_enabled ? <StatusBadge tone={defaultStatusTone(liveStatus)}>
              <span className="capitalize">{liveStatus.replace('_', ' ')}</span>
            </StatusBadge> : null}
          </div>

          {!printer.monitor_enabled ? (
            <div className="rounded-md border border-dashed border-border bg-background p-6 text-sm text-muted-foreground">
              Monitoring is not configured for this printer yet. The machine is still available as a static tracked record.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-md border border-border bg-background p-4">
                  <p className="text-xs text-muted-foreground">Provider</p>
                  <p className="mt-2 font-semibold capitalize text-foreground">{printer.monitor_provider || '—'}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{printer.monitor_poll_interval_seconds}s poll interval</p>
                </div>
                <div className="rounded-md border border-border bg-background p-4">
                  <p className="text-xs text-muted-foreground">Last event</p>
                  <p className="mt-2 font-semibold text-foreground">
                    {printer.monitor_last_event_type ? printer.monitor_last_event_type.replace('notify_', '').replaceAll('_', ' ') : '—'}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">{formatDateTime(printer.monitor_last_event_at)}</p>
                </div>
                <div className="rounded-md border border-border bg-background p-4">
                  <p className="text-xs text-muted-foreground">Last seen</p>
                  <p className="mt-2 font-semibold text-foreground">{formatDateTime(printer.monitor_last_seen_at)}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {printer.monitor_provider === 'moonraker'
                      ? printer.monitor_ws_connected
                        ? 'WebSocket receiving live events'
                        : 'Socket stale, polling fallback'
                      : 'Polled provider'}
                  </p>
                </div>
              </div>

              <div className="rounded-md border border-border bg-background p-4">
                <p className="text-xs text-muted-foreground">Provider message</p>
                <p className="mt-2 text-sm text-foreground">{printer.monitor_last_message || '—'}</p>
              </div>

              {printer.monitor_last_error ? (
                <div className="rounded-md border border-red-300/60 bg-red-50/80 p-4 dark:border-red-500/30 dark:bg-red-500/10">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
                    <div>
                      <p className="text-xs text-destructive">Last monitor error</p>
                      <p className="mt-2 text-sm text-destructive">{printer.monitor_last_error}</p>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </section>

        <section className="rounded-md border border-border bg-card p-5 shadow-xs">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">Visual console</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {printer.camera_id ? `Live feed from ${printer.camera_name}` : 'Current print thumbnail plus the most relevant assignment and machine details.'}
              </p>
            </div>
            {printer.camera_id && (
              <Button asChild variant="outline" size="sm">
                <Link to={`/print-floor/monitor/${printer.id}`}>
                  <Expand className="h-3.5 w-3.5" />
                  Monitor
                </Link>
              </Button>
            )}
          </div>

          {printer.camera_mse_ws_url || printer.camera_snapshot_url ? (
            <CameraFeed
              mseWsUrl={printer.camera_mse_ws_url}
              snapshotUrl={printer.camera_snapshot_url}
              alt={`${printer.name} camera feed`}
              className="min-h-[280px] rounded-md"
            />
          ) : (
            <PrinterThumbnail
              src={printer.current_print_thumbnail_url}
              alt={printer.current_print_name ? `${printer.current_print_name} thumbnail` : `${printer.name} current print thumbnail`}
              className="min-h-[280px] rounded-md"
              fallbackLabel={printer.current_print_name ? 'No thumbnail in G-code metadata' : 'No active print'}
            />
          )}

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-border bg-background p-4">
              <p className="text-xs text-muted-foreground">Machine identity</p>
              <p className="mt-2 font-semibold text-foreground">{printer.manufacturer || '—'} {printer.model || ''}</p>
              <p className="mt-1 text-sm text-muted-foreground">{printer.serial_number || 'No serial number'}</p>
            </div>
            <div className="rounded-md border border-border bg-background p-4">
              <p className="text-xs text-muted-foreground">Current assignment</p>
              {activeJob ? (
                <>
                  <Link to={`/orders/jobs/${activeJob.id}`} className="mt-2 block font-semibold text-primary no-underline hover:underline">
                    {activeJob.job_number}
                  </Link>
                  <p className="mt-1 text-sm text-muted-foreground">{activeJob.product_name}</p>
                </>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">No draft or in-progress job assigned.</p>
              )}
            </div>
          </div>

          {printer.notes ? (
            <div className="mt-4 rounded-md border border-border bg-background p-4">
              <p className="text-xs text-muted-foreground">Notes</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">{printer.notes}</p>
            </div>
          ) : null}
        </section>
      </div>

      <section className="rounded-md border border-border bg-card p-5 shadow-xs">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-foreground">Recent floor activity</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Status changes and assignment events for this machine.
            </p>
          </div>
          <span className="rounded-full bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground">
            {printer.history_events.length} events
          </span>
        </div>

        {!printer.history_events.length ? (
          <div className="rounded-md border border-dashed border-border bg-background p-6 text-sm text-muted-foreground">
            No printer activity has been recorded yet.
          </div>
        ) : (
          <div className="space-y-3">
            {printer.history_events.map((event) => {
              const jobNumber = formatEventMetaValue(event.metadata?.job_number);
              const fromStatus = formatEventMetaValue(event.metadata?.from_status);
              const toStatus = formatEventMetaValue(event.metadata?.to_status);
              const fromPrinter = formatEventMetaValue(event.metadata?.from_printer_name);
              const toPrinter = formatEventMetaValue(event.metadata?.to_printer_name);
              return (
                <div key={event.id} className="rounded-md border border-border bg-background p-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-medium text-foreground">{event.title}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{event.description || '—'}</p>
                    </div>
                    <div className="text-xs text-muted-foreground sm:text-right">
                      <p>{formatDateTime(event.created_at)}</p>
                      <p>{event.actor_name || 'System'}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {jobNumber ? <span className="rounded-full bg-card px-2.5 py-1">Job {jobNumber}</span> : null}
                    {fromStatus || toStatus ? <span className="rounded-full bg-card px-2.5 py-1">{fromStatus || '—'} → {toStatus || '—'}</span> : null}
                    {fromPrinter || toPrinter ? <span className="rounded-full bg-card px-2.5 py-1">{fromPrinter || 'Unassigned'} → {toPrinter || 'Unassigned'}</span> : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="rounded-md border border-border bg-card p-5 shadow-xs">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-foreground">Assigned jobs</h2>
            <p className="mt-1 text-sm text-muted-foreground">Current and recent jobs routed through this printer.</p>
          </div>
          <Link to="/orders" className="text-sm text-primary no-underline hover:underline">
            View all jobs
          </Link>
        </div>

        {jobsLoading ? (
          <SkeletonTable rows={5} cols={6} />
        ) : !recentJobs.length ? (
          <div className="rounded-md border border-dashed border-border bg-background p-8 text-center text-muted-foreground">
            No jobs assigned to this printer yet.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border border-border bg-background">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Job #</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Product</th>
                  <th className="px-4 py-3 font-medium text-right">Pieces</th>
                  <th className="px-4 py-3 font-medium text-right">Revenue</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.map((job: Job) => (
                  <tr key={job.id} className="border-b border-border last:border-0 hover:bg-accent/40">
                    <td className="px-4 py-3">
                      <Link to={`/orders/jobs/${job.id}`} className="font-medium text-primary no-underline hover:underline">
                        {job.job_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{job.date}</td>
                    <td className="px-4 py-3">{job.product_name}</td>
                    <td className="px-4 py-3 text-right">{job.total_pieces}</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(job.total_revenue)}</td>
                    <td className="px-4 py-3">
                      <StatusBadge tone={defaultStatusTone(job.status)}>
                        <span className="capitalize">{job.status.replace('_', ' ')}</span>
                      </StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <ConfirmDialog
        open={confirmToggle}
        onOpenChange={setConfirmToggle}
        title={printer.is_active ? 'Deactivate printer?' : 'Restore printer?'}
        description={
          printer.is_active
            ? `${printer.name} will preserve historical assignments and be removed from active use.`
            : `${printer.name} will be restored to active printers.`
        }
        confirmLabel={printer.is_active ? 'Deactivate' : 'Restore'}
        tone={printer.is_active ? 'destructive' : 'default'}
        onConfirm={toggleActive}
      />
    </div>
  );
}
