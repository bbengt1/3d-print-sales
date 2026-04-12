import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  Boxes,
  ClipboardList,
  Eye,
  PackageOpen,
  Printer,
  Receipt,
  TriangleAlert,
  User,
} from 'lucide-react';
import api from '@/api/client';
import EmptyState from '@/components/ui/EmptyState';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { cn, formatCurrency } from '@/lib/utils';
import type { Customer, Job, PaginatedJobs, PaginatedPrinters, PaginatedSales, SaleListItem } from '@/types';

const ATTENTION_PRINTER_STATUSES = new Set(['paused', 'maintenance', 'offline', 'error']);

function QueueStat({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-black/20 px-4 py-4">
      <p className="text-xs uppercase tracking-[0.24em] text-white/55">{label}</p>
      <p className="mt-3 text-2xl font-semibold">{value}</p>
      <p className="mt-2 text-sm text-white/70">{detail}</p>
    </div>
  );
}

function statusTone(status: string) {
  if (status === 'completed' || status === 'delivered' || status === 'shipped') {
    return 'bg-emerald-50 text-emerald-900 border-emerald-300/50';
  }
  if (status === 'in_progress' || status === 'paid' || status === 'printing') {
    return 'bg-blue-50 text-blue-900 border-blue-300/50';
  }
  if (status === 'pending' || status === 'draft') {
    return 'bg-amber-50 text-amber-900 border-amber-300/50';
  }
  return 'bg-slate-100 text-slate-800 border-slate-300/50';
}

export default function OrdersPage() {
  const [jobStatusFilter, setJobStatusFilter] = useState<'all' | 'needs-assignment' | 'in-progress' | 'draft'>('all');

  const { data: jobsData, isLoading: jobsLoading } = useQuery<PaginatedJobs>({
    queryKey: ['jobs', 'orders-queue'],
    queryFn: () => api.get('/jobs?limit=50').then((r) => r.data),
  });

  const { data: salesData, isLoading: salesLoading } = useQuery<PaginatedSales>({
    queryKey: ['sales', 'orders-queue'],
    queryFn: () => api.get('/sales?limit=20').then((r) => r.data),
  });

  const { data: printersData, isLoading: printersLoading } = useQuery<PaginatedPrinters>({
    queryKey: ['printers', 'orders-queue'],
    queryFn: () => api.get('/printers?is_active=true&limit=100').then((r) => r.data),
  });

  const { data: customers = [], isLoading: customersLoading } = useQuery<Customer[]>({
    queryKey: ['customers', 'orders-queue'],
    queryFn: () => api.get('/customers').then((r) => r.data),
  });

  const jobs = jobsData?.items || [];
  const sales = salesData?.items || [];
  const printers = printersData?.items || [];

  const jobsNeedingAssignment = jobs.filter(
    (job) => job.status !== 'completed' && job.status !== 'cancelled' && !job.printer_id
  );
  const productionActive = jobs.filter((job) => job.status === 'in_progress');
  const draftJobs = jobs.filter((job) => job.status === 'draft');
  const fulfillmentSales = sales.filter((sale) => sale.status === 'pending' || sale.status === 'paid');
  const readyPrinters = printers.filter((printer) => (printer.monitor_status || printer.status) === 'idle');
  const attentionPrinters = printers.filter((printer) =>
    ATTENTION_PRINTER_STATUSES.has(printer.monitor_status || printer.status)
  );
  const topCustomers = [...customers].sort((a, b) => b.job_count - a.job_count).slice(0, 5);

  const visibleJobs = useMemo(() => {
    switch (jobStatusFilter) {
      case 'needs-assignment':
        return jobsNeedingAssignment;
      case 'in-progress':
        return productionActive;
      case 'draft':
        return draftJobs;
      default:
        return jobs.slice(0, 12);
    }
  }, [draftJobs, jobStatusFilter, jobs, jobsNeedingAssignment, productionActive]);

  const loading = jobsLoading || salesLoading || printersLoading;

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-border bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.16),_transparent_24%),linear-gradient(135deg,_rgba(8,17,31,1),_rgba(16,33,52,0.98)_48%,_rgba(27,55,44,0.96)_100%)] p-6 text-white shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm uppercase tracking-[0.3em] text-white/65">Orders Workspace</p>
            <h1 className="mt-3 flex items-center gap-3 text-3xl font-bold">
              <ClipboardList className="h-8 w-8" />
              Production and fulfillment queue
            </h1>
            <p className="mt-3 text-sm text-white/80">
              Bring together print jobs, fulfillment-relevant sales, and printer readiness so floor and owner workflows stop bouncing between unrelated pages.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              to="/orders/jobs/new"
              className="inline-flex min-h-12 items-center gap-2 rounded-2xl bg-primary px-5 py-3 font-semibold text-primary-foreground no-underline transition-opacity hover:opacity-90"
            >
              <PackageOpen className="h-4 w-4" />
              New job
            </Link>
            <Link
              to="/orders/jobs"
              className="inline-flex min-h-12 items-center gap-2 rounded-2xl border border-white/20 bg-white/10 px-5 py-3 font-semibold text-white no-underline transition-colors hover:bg-white/15"
            >
              Open jobs
            </Link>
          </div>
        </div>

        <div className="mt-6 grid gap-3 lg:grid-cols-4">
          <QueueStat label="Needs Assignment" value={String(jobsNeedingAssignment.length)} detail="Jobs without a printer assignment" />
          <QueueStat label="In Progress" value={String(productionActive.length)} detail="Jobs currently on the production floor" />
          <QueueStat label="Fulfillment Queue" value={String(fulfillmentSales.length)} detail="Sales still pending shipment/delivery follow-up" />
          <QueueStat label="Ready Printers" value={String(readyPrinters.length)} detail="Idle printers available for reassignment" />
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.92fr)]">
        <section className="space-y-6">
          <div className="rounded-3xl border border-border bg-card p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Boxes className="h-5 w-5 text-muted-foreground" />
                  <h2 className="text-xl font-semibold">Production queue</h2>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Surface missing printer assignments first, then the active floor queue. The existing job detail pages stay intact behind these links.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  ['all', 'All queue', `${jobs.length} recent jobs`],
                  ['needs-assignment', 'Needs assignment', `${jobsNeedingAssignment.length} jobs`],
                  ['in-progress', 'In progress', `${productionActive.length} jobs`],
                  ['draft', 'Draft', `${draftJobs.length} jobs`],
                ].map(([value, label, detail]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setJobStatusFilter(value as typeof jobStatusFilter)}
                    className={cn(
                      'rounded-2xl border px-4 py-3 text-left transition-colors',
                      jobStatusFilter === value
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-background hover:border-primary/35'
                    )}
                  >
                    <p className="text-sm font-semibold">{label}</p>
                    <p className={cn('mt-1 text-xs', jobStatusFilter === value ? 'text-primary-foreground/80' : 'text-muted-foreground')}>
                      {detail}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <div className="mt-4">
                <SkeletonTable rows={5} cols={6} />
              </div>
            ) : !visibleJobs.length ? (
              <EmptyState
                icon="jobs"
                title="No queue items in this view"
                description="Try another queue filter or open the full jobs list."
                className="py-10"
              />
            ) : (
              <div className="mt-4 space-y-3">
                {visibleJobs.map((job: Job) => {
                  const missingAssignment = !job.printer_id && job.status !== 'completed' && job.status !== 'cancelled';
                  return (
                    <div key={job.id} className={cn('rounded-2xl border p-4', missingAssignment ? 'border-amber-300/60 bg-amber-50/70' : 'border-border bg-background/80')}>
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <Link to={`/orders/jobs/${job.id}`} className="font-semibold text-foreground no-underline hover:underline">
                              {job.job_number}
                            </Link>
                            <span className={cn('rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize', statusTone(job.status))}>
                              {job.status.replace('_', ' ')}
                            </span>
                            {missingAssignment ? (
                              <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-900">
                                Missing printer
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-2 text-sm font-medium">{job.product_name}</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {job.customer_name || 'No customer'} • {job.total_pieces} pieces • {formatCurrency(job.total_revenue)}
                          </p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Printer: {job.printer?.name || 'Unassigned'}
                          </p>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          {job.printer ? (
                            <Link
                              to={`/print-floor/printers/${job.printer.id}`}
                              className="inline-flex items-center gap-2 rounded-xl border border-border px-3 py-2 text-sm font-semibold text-foreground no-underline transition-colors hover:bg-accent"
                            >
                              <Printer className="h-4 w-4" />
                              Printer
                            </Link>
                          ) : null}
                          <Link
                            to={`/orders/jobs/${job.id}`}
                            className="inline-flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground no-underline transition-opacity hover:opacity-90"
                          >
                            <Eye className="h-4 w-4" />
                            Open job
                          </Link>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="rounded-3xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Receipt className="h-5 w-5 text-muted-foreground" />
                  <h2 className="text-xl font-semibold">Fulfillment-relevant sales</h2>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  First pass uses existing sales statuses to surface orders most likely to need packaging or shipment follow-up.
                </p>
              </div>
              <Link
                to="/sell/sales"
                className="inline-flex items-center gap-2 rounded-2xl border border-border px-4 py-2 text-sm font-semibold text-foreground no-underline transition-colors hover:bg-accent"
              >
                Open sales inbox
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            {!fulfillmentSales.length ? (
              <p className="mt-4 text-sm text-muted-foreground">No pending or paid sales in the current queue window.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {fulfillmentSales.slice(0, 8).map((sale: SaleListItem) => (
                  <div key={sale.id} className="rounded-2xl border border-border bg-background/80 p-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Link to={`/sell/sales/${sale.id}`} className="font-semibold text-foreground no-underline hover:underline">
                            {sale.sale_number}
                          </Link>
                          <span className={cn('rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize', statusTone(sale.status))}>
                            {sale.status}
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {sale.customer_name || 'Guest'} • {sale.channel_name || 'Direct'} • {sale.item_count} items
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold">{formatCurrency(sale.total)}</p>
                        <p className="text-xs text-muted-foreground capitalize">{sale.payment_method || 'Unknown payment'}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <TriangleAlert className="h-5 w-5 text-amber-600" />
              <h2 className="text-xl font-semibold">Assignment pressure</h2>
            </div>
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl bg-background px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Unassigned jobs</p>
                <p className="mt-2 text-2xl font-semibold">{jobsNeedingAssignment.length}</p>
                <p className="mt-1 text-sm text-muted-foreground">Jobs that need printer selection or reassignment.</p>
              </div>
              <div className="rounded-2xl bg-background px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Ready printers</p>
                <p className="mt-2 text-2xl font-semibold">{readyPrinters.length}</p>
                <p className="mt-1 text-sm text-muted-foreground">Idle machines available for production work.</p>
              </div>
              <div className="rounded-2xl bg-background px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Attention printers</p>
                <p className="mt-2 text-2xl font-semibold">{attentionPrinters.length}</p>
                <p className="mt-1 text-sm text-muted-foreground">Paused, offline, maintenance, or error states.</p>
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <User className="h-5 w-5 text-muted-foreground" />
                <h2 className="text-xl font-semibold">Customer load</h2>
              </div>
              <Link
                to="/orders/customers"
                className="inline-flex items-center gap-2 rounded-2xl border border-border px-4 py-2 text-sm font-semibold text-foreground no-underline transition-colors hover:bg-accent"
              >
                Open customers
              </Link>
            </div>

            {customersLoading ? (
              <div className="mt-4">
                <SkeletonTable rows={4} cols={2} />
              </div>
            ) : !topCustomers.length ? (
              <p className="mt-4 text-sm text-muted-foreground">No customer activity yet.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {topCustomers.map((customer) => (
                  <div key={customer.id} className="rounded-2xl border border-border bg-background/80 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{customer.name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{customer.email || customer.phone || 'No contact info'}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-semibold">{customer.job_count}</p>
                        <p className="text-xs text-muted-foreground">jobs</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-xl font-semibold">Known gap</h2>
            <p className="mt-3 text-sm text-muted-foreground">
              This first pass stitches jobs, sales, printers, and customers client-side. Quote-specific queueing and a dedicated backend fulfillment queue endpoint are still separate follow-on work.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
