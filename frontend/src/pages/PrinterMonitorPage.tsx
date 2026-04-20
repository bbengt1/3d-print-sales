import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Thermometer, Clock, Layers, Wifi, WifiOff } from 'lucide-react';
import api from '@/api/client';
import type { Printer } from '@/types';
import CameraFeed from '@/components/cameras/CameraFeed';
import { Skeleton } from '@/components/ui/Skeleton';

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return '--';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatTemp(c: number | null | undefined): string {
  if (c == null) return '--';
  return `${c.toFixed(0)}°C`;
}

export default function PrinterMonitorPage() {
  const { id } = useParams<{ id: string }>();

  const { data: printer, isLoading } = useQuery<Printer>({
    queryKey: ['printer-monitor', id],
    queryFn: () => api.get(`/printers/${id}`).then((r) => r.data),
    refetchInterval: 30_000,
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="h-screen w-screen bg-slate-950 flex items-center justify-center">
        <Skeleton className="h-6 w-40" />
        <span className="sr-only">Loading printer</span>
      </div>
    );
  }

  if (!printer) {
    return (
      <div className="h-screen w-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <p className="text-lg font-medium">Printer not found</p>
          <Link to="/print-floor" className="text-primary text-sm mt-2 inline-block hover:underline">
            Back to Print Floor
          </Link>
        </div>
      </div>
    );
  }

  const status = printer.monitor_status || printer.status;
  const progress = printer.monitor_progress_percent;
  const hasCamera = !!printer.camera_mse_ws_url || !!printer.camera_snapshot_url;

  const statusColor =
    status === 'printing'
      ? 'text-primary'
      : status === 'error'
        ? 'text-destructive'
        : status === 'paused'
          ? 'text-warning'
          : 'text-muted-foreground';

  return (
    <div className="h-screen w-screen bg-slate-950 flex flex-col overflow-hidden">
      {/* Camera feed area — fills most of the screen */}
      <div className="flex-1 min-h-0 relative">
        {hasCamera ? (
          <CameraFeed
            mseWsUrl={printer.camera_mse_ws_url}
            snapshotUrl={printer.camera_snapshot_url}
            alt={`${printer.name} camera feed`}
            className="w-full h-full"
            showLiveBadge
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <p className="text-lg">No camera assigned</p>
              <p className="text-sm mt-1 opacity-60">
                Assign a camera to this printer in Admin &gt; Cameras
              </p>
            </div>
          </div>
        )}

        {/* Back button (top-left, translucent) */}
        <Link
          to={`/print-floor/printers/${printer.id}`}
          className="absolute top-4 left-4 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-black/60 text-white/80 hover:text-white text-xs font-medium backdrop-blur-sm transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Exit Monitor
        </Link>
      </div>

      {/* Bottom telemetry strip */}
      <div className="shrink-0 bg-gradient-to-t from-black/95 to-black/80 backdrop-blur-sm border-t border-white/5 px-6 py-4">
        <div className="flex items-center justify-between gap-6 max-w-7xl mx-auto">
          {/* Printer identity */}
          <div className="min-w-0">
            <h1 className="text-white text-lg font-display font-semibold truncate">{printer.name}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`text-sm font-medium capitalize ${statusColor}`}>{status}</span>
              {printer.current_print_name && (
                <span className="text-xs text-white/50 truncate max-w-[200px]">
                  {printer.current_print_name}
                </span>
              )}
            </div>
          </div>

          {/* Progress bar (center) */}
          {status === 'printing' && progress != null && (
            <div className="flex-1 max-w-md">
              <div className="flex items-center justify-between text-xs text-white/60 mb-1">
                <span>Progress</span>
                <span className="font-medium text-white">{progress.toFixed(1)}%</span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-1000"
                  style={{ width: `${Math.min(progress, 100)}%` }}
                />
              </div>
            </div>
          )}

          {/* Telemetry stats */}
          <div className="flex items-center gap-5 shrink-0">
            {/* ETA */}
            <div className="flex items-center gap-1.5 text-white/70">
              <Clock className="h-4 w-4" />
              <span className="text-sm">{formatDuration(printer.monitor_remaining_seconds)}</span>
            </div>

            {/* Layers */}
            <div className="flex items-center gap-1.5 text-white/70">
              <Layers className="h-4 w-4" />
              <span className="text-sm">
                {printer.monitor_current_layer ?? '--'}/{printer.monitor_total_layers ?? '--'}
              </span>
            </div>

            {/* Nozzle temp */}
            <div className="flex items-center gap-1.5 text-white/70" title="Nozzle">
              <Thermometer className="h-4 w-4 text-destructive/70" />
              <span className="text-sm">{formatTemp(printer.monitor_tool_temp_c)}</span>
            </div>

            {/* Bed temp */}
            <div className="flex items-center gap-1.5 text-white/70" title="Bed">
              <Thermometer className="h-4 w-4 text-info/70" />
              <span className="text-sm">{formatTemp(printer.monitor_bed_temp_c)}</span>
            </div>

            {/* Connection */}
            <div className="flex items-center gap-1.5">
              {printer.monitor_ws_connected ? (
                <Wifi className="h-4 w-4 text-primary/70" />
              ) : (
                <WifiOff className="h-4 w-4 text-muted-foreground/50" />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
