import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Edit, Archive, ArchiveRestore } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { cn, formatCurrency } from '@/lib/utils';
import { SkeletonTable } from '@/components/ui/Skeleton';
import type { Job, PaginatedJobs, Printer } from '@/types';

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

function StatusBadge({ status }: { status: string }) {
  return <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize', statusClasses[status] || 'bg-primary/10 text-primary')}>{status.replace('_', ' ')}</span>;
}

export default function PrinterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: printer, isLoading: printerLoading } = useQuery<Printer>({
    queryKey: ['printer', id],
    queryFn: () => api.get(`/printers/${id}`).then((response) => response.data),
    enabled: Boolean(id),
  });

  const { data: jobs, isLoading: jobsLoading } = useQuery<PaginatedJobs>({
    queryKey: ['printer-jobs', id],
    queryFn: () => api.get('/jobs', { params: { printer_id: id, limit: 10 } }).then((response) => response.data),
    enabled: Boolean(id),
  });

  const toggleActive = async () => {
    if (!printer) return;
    const confirmed = window.confirm(
      printer.is_active
        ? `Deactivate ${printer.name}?\n\nThis preserves historical assignments and removes it from active use.`
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

  if (printerLoading) return <SkeletonTable rows={4} cols={4} />;
  if (!printer) return <p className="py-16 text-center text-muted-foreground">Printer not found</p>;

  const recentJobs = jobs?.items || [];
  const activeJob = recentJobs.find((job) => job.status === 'in_progress' || job.status === 'draft');

  return (
    <div className="max-w-5xl mx-auto">
      <Link to="/printers" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4 no-underline">
        <ArrowLeft className="w-4 h-4" /> Back to Printers
      </Link>

      <div className="rounded-lg border border-border bg-card p-6 mb-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <h1 className="text-2xl font-bold">{printer.name}</h1>
              <StatusBadge status={printer.status} />
              <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', printer.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400')}>
                {printer.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="text-sm text-muted-foreground font-mono">{printer.slug}</p>
            {!printer.is_active && <p className="mt-2 text-sm text-muted-foreground">This printer is inactive. Historical job assignments are still preserved.</p>}
          </div>

          <div className="flex flex-wrap gap-2">
            <Link to={`/printers/${printer.id}/edit`} className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 no-underline hover:bg-accent">
              <Edit className="w-4 h-4" /> Edit
            </Link>
            <button onClick={toggleActive} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-4 py-2 hover:bg-accent">
              {printer.is_active ? <Archive className="w-4 h-4" /> : <ArchiveRestore className="w-4 h-4" />}
              {printer.is_active ? 'Deactivate' : 'Restore'}
            </button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mt-6">
          <div>
            <p className="text-xs text-muted-foreground">Manufacturer</p>
            <p className="text-lg font-semibold">{printer.manufacturer || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Model</p>
            <p className="text-lg font-semibold">{printer.model || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Location</p>
            <p className="text-lg font-semibold">{printer.location || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Serial Number</p>
            <p className="text-lg font-semibold">{printer.serial_number || '—'}</p>
          </div>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="rounded-lg border border-border bg-background/40 p-4">
            <p className="text-xs text-muted-foreground mb-1">Notes</p>
            <p className="text-sm whitespace-pre-wrap">{printer.notes || 'No notes yet.'}</p>
          </div>
          <div className="rounded-lg border border-border bg-background/40 p-4">
            <p className="text-xs text-muted-foreground mb-1">Current / recent assignment</p>
            {activeJob ? (
              <div>
                <p className="font-semibold">{activeJob.job_number}</p>
                <p className="text-sm text-muted-foreground">{activeJob.product_name}</p>
                <p className="text-xs text-muted-foreground mt-1">{activeJob.total_pieces} pcs · {activeJob.date}</p>
              </div>
            ) : recentJobs[0] ? (
              <div>
                <p className="font-semibold">{recentJobs[0].job_number}</p>
                <p className="text-sm text-muted-foreground">Last assigned: {recentJobs[0].product_name}</p>
                <p className="text-xs text-muted-foreground mt-1">{recentJobs[0].date}</p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No jobs assigned yet.</p>
            )}
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold">Assigned Jobs</h2>
            <p className="text-sm text-muted-foreground">Current and recent jobs for this printer.</p>
          </div>
          <Link to="/jobs" className="text-sm text-primary no-underline hover:underline">View all jobs</Link>
        </div>

        {jobsLoading ? (
          <SkeletonTable rows={5} cols={6} />
        ) : !recentJobs.length ? (
          <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">No jobs assigned to this printer yet.</div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border bg-card">
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
                  <tr key={job.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                    <td className="px-4 py-3"><Link to={`/jobs/${job.id}`} className="font-medium text-primary no-underline hover:underline">{job.job_number}</Link></td>
                    <td className="px-4 py-3">{job.date}</td>
                    <td className="px-4 py-3">{job.product_name}</td>
                    <td className="px-4 py-3 text-right">{job.total_pieces}</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(job.total_revenue)}</td>
                    <td className="px-4 py-3">
                      <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', jobStatusClasses[job.status] || 'bg-primary/10 text-primary')}>
                        {job.status.replace('_', ' ')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
