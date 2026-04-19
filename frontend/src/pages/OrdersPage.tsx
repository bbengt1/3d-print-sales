import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  Boxes,
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
import PageHeader from '@/components/layout/PageHeader';
import { KPI, KPIStrip } from '@/components/layout/KPIStrip';
import { cn, formatCurrency } from '@/lib/utils';
import type { Customer, Job, PaginatedJobs, PaginatedPrinters, PaginatedSales, SaleListItem } from '@/types';

const ATTENTION_PRINTER_STATUSES = new Set(['paused', 'maintenance', 'offline', 'error']);

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
      <PageHeader
        title="Orders"
        description={
          jobsNeedingAssignment.length > 0
            ? `${jobsNeedingAssignment.length} ${jobsNeedingAssignment.length === 1 ? 'job needs' : 'jobs need'} a printer assignment`
            : 'Production and fulfillment queue'
        }
        actions={
          <>
            <Link
              to="/orders/jobs/new"
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground no-underline transition-opacity hover:opacity-90"
            >
              <PackageOpen className="h-4 w-4" />
              New job
            </Link>
            <Link
              to="/orders/jobs"
              className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium no-underline hover:bg-muted transition-colors"
            >
              Open jobs
            </Link>
          </>
        }
      >
        <KPIStrip columns={4}>
          <KPI
            label="Needs assignment"
            value={jobsNeedingAssignment.length}
            sub="Jobs missing a printer"
            tone={jobsNeedingAssignment.length > 0 ? 'warning' : 'default'}
          />
          <KPI
            label="In progress"
            value={productionActive.length}
            sub="Jobs on the production floor"
          />
          <KPI
            label="Fulfillment queue"
            value={fulfillmentSales.length}
            sub="Sales pending ship/deliver"
          />
          <KPI
            label="Ready printers"
            value={readyPrinters.length}
            sub="Idle, available for assignment"
            tone={readyPrinters.length === 0 ? 'warning' : 'default'}
          />
        </KPIStrip>
      </PageHeader>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.92fr)]">
        <section className="space-y-6">
          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
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
                      'rounded-md border px-4 py-3 text-left transition-colors',
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
                    <div key={job.id} className={cn('rounded-md border p-4', missingAssignment ? 'border-amber-300/60 bg-amber-50/70' : 'border-border bg-background/80')}>
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

          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
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
                className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-semibold text-foreground no-underline transition-colors hover:bg-accent"
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
                  <div key={sale.id} className="rounded-md border border-border bg-background/80 p-4">
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
          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <TriangleAlert className="h-5 w-5 text-amber-600" />
              <h2 className="text-xl font-semibold">Assignment pressure</h2>
            </div>
            <div className="mt-4 space-y-3">
              <div className="rounded-md bg-background px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Unassigned jobs</p>
                <p className="mt-2 text-2xl font-semibold">{jobsNeedingAssignment.length}</p>
                <p className="mt-1 text-sm text-muted-foreground">Jobs that need printer selection or reassignment.</p>
              </div>
              <div className="rounded-md bg-background px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Ready printers</p>
                <p className="mt-2 text-2xl font-semibold">{readyPrinters.length}</p>
                <p className="mt-1 text-sm text-muted-foreground">Idle machines available for production work.</p>
              </div>
              <div className="rounded-md bg-background px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Attention printers</p>
                <p className="mt-2 text-2xl font-semibold">{attentionPrinters.length}</p>
                <p className="mt-1 text-sm text-muted-foreground">Paused, offline, maintenance, or error states.</p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <User className="h-5 w-5 text-muted-foreground" />
                <h2 className="text-xl font-semibold">Customer load</h2>
              </div>
              <Link
                to="/orders/customers"
                className="inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-semibold text-foreground no-underline transition-colors hover:bg-accent"
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
                  <div key={customer.id} className="rounded-md border border-border bg-background/80 px-4 py-3">
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

          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
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
