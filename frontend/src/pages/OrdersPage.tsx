import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, PackageOpen, Printer as PrinterIcon, TriangleAlert, User } from 'lucide-react';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import { KPI, KPIStrip } from '@/components/layout/KPIStrip';
import DataTable, { type Column } from '@/components/data/DataTable';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import { Button } from '@/components/ui/Button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { formatCurrency } from '@/lib/utils';
import type {
  Customer,
  Job,
  PaginatedJobs,
  PaginatedPrinters,
  PaginatedSales,
  SaleListItem,
} from '@/types';

const ATTENTION_PRINTER_STATUSES = new Set(['paused', 'maintenance', 'offline', 'error']);

type QueueFilter = 'all' | 'needs-assignment' | 'in-progress' | 'draft';

export default function OrdersPage() {
  const navigate = useNavigate();
  const [queueFilter, setQueueFilter] = useState<QueueFilter>('all');

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

  const { data: customers = [] } = useQuery<Customer[]>({
    queryKey: ['customers', 'orders-queue'],
    queryFn: () => api.get('/customers').then((r) => r.data),
  });

  const jobs = jobsData?.items || [];
  const sales = salesData?.items || [];
  const printers = printersData?.items || [];

  const jobsNeedingAssignment = jobs.filter(
    (job) => job.status !== 'completed' && job.status !== 'cancelled' && !job.printer_id,
  );
  const productionActive = jobs.filter((job) => job.status === 'in_progress');
  const draftJobs = jobs.filter((job) => job.status === 'draft');
  const fulfillmentSales = sales.filter((sale) => sale.status === 'pending' || sale.status === 'paid');
  const readyPrinters = printers.filter((printer) => (printer.monitor_status || printer.status) === 'idle');
  const attentionPrinters = printers.filter((printer) =>
    ATTENTION_PRINTER_STATUSES.has(printer.monitor_status || printer.status),
  );
  const topCustomers = [...customers].sort((a, b) => b.job_count - a.job_count).slice(0, 5);

  const visibleJobs = useMemo(() => {
    switch (queueFilter) {
      case 'needs-assignment':
        return jobsNeedingAssignment;
      case 'in-progress':
        return productionActive;
      case 'draft':
        return draftJobs;
      default:
        return jobs.slice(0, 20);
    }
  }, [queueFilter, jobs, jobsNeedingAssignment, productionActive, draftJobs]);

  const jobColumns: Column<Job>[] = [
    {
      key: 'job_number',
      header: 'Job',
      cell: (j) => <span className="font-medium text-foreground">{j.job_number}</span>,
    },
    {
      key: 'product_name',
      header: 'Product',
      cell: (j) => <span className="truncate">{j.product_name}</span>,
    },
    {
      key: 'customer_name',
      header: 'Customer',
      colClassName: 'hidden md:table-cell',
      cell: (j) => j.customer_name || <span className="text-muted-foreground">—</span>,
    },
    {
      key: 'total_pieces',
      header: 'Pieces',
      numeric: true,
      cell: (j) => j.total_pieces,
    },
    {
      key: 'total_revenue',
      header: 'Revenue',
      numeric: true,
      cell: (j) => formatCurrency(j.total_revenue),
    },
    {
      key: 'printer',
      header: 'Printer',
      colClassName: 'hidden lg:table-cell',
      cell: (j) =>
        j.printer ? (
          <span className="text-foreground">{j.printer.name}</span>
        ) : (
          <span className="inline-flex items-center gap-1 text-amber-700 dark:text-amber-300">
            <TriangleAlert className="h-3 w-3" aria-hidden="true" />
            Unassigned
          </span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      cell: (j) => (
        <StatusBadge tone={defaultStatusTone(j.status)}>{j.status.replace('_', ' ')}</StatusBadge>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '120px',
      cell: (j) => (
        <div className="flex justify-end gap-1">
          {j.printer ? (
            <Button asChild variant="ghost" size="sm">
              <Link
                to={`/print-floor/printers/${j.printer.id}`}
                onClick={(e) => e.stopPropagation()}
                aria-label={`Open ${j.printer.name}`}
              >
                <PrinterIcon className="h-3.5 w-3.5" />
              </Link>
            </Button>
          ) : null}
          <Button asChild variant="outline" size="sm">
            <Link
              to={`/orders/jobs/${j.id}`}
              onClick={(e) => e.stopPropagation()}
            >
              Open
            </Link>
          </Button>
        </div>
      ),
    },
  ];

  const saleColumns: Column<SaleListItem>[] = [
    {
      key: 'sale_number',
      header: 'Sale',
      cell: (s) => <span className="font-medium text-foreground">{s.sale_number}</span>,
    },
    {
      key: 'customer_name',
      header: 'Customer',
      cell: (s) => s.customer_name || <span className="text-muted-foreground">Guest</span>,
    },
    {
      key: 'channel_name',
      header: 'Channel',
      colClassName: 'hidden md:table-cell',
      cell: (s) => s.channel_name || <span className="text-muted-foreground">Direct</span>,
    },
    {
      key: 'item_count',
      header: 'Items',
      numeric: true,
      cell: (s) => s.item_count,
    },
    {
      key: 'total',
      header: 'Total',
      numeric: true,
      cell: (s) => formatCurrency(s.total),
    },
    {
      key: 'payment_method',
      header: 'Payment',
      colClassName: 'hidden lg:table-cell',
      cell: (s) => (
        <span className="capitalize text-muted-foreground">{s.payment_method || 'Unknown'}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      cell: (s) => <StatusBadge tone={defaultStatusTone(s.status)}>{s.status}</StatusBadge>,
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '88px',
      cell: (s) => (
        <div className="flex justify-end">
          <Button asChild variant="outline" size="sm">
            <Link to={`/sell/sales/${s.id}`} onClick={(e) => e.stopPropagation()}>
              Open
            </Link>
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Orders"
        description={
          jobsNeedingAssignment.length > 0
            ? `${jobsNeedingAssignment.length} ${jobsNeedingAssignment.length === 1 ? 'job needs' : 'jobs need'} a printer assignment`
            : 'Production and fulfillment queue.'
        }
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/orders/jobs">Open jobs</Link>
            </Button>
            <Button asChild>
              <Link to="/orders/jobs/new">
                <PackageOpen className="h-4 w-4" /> New job
              </Link>
            </Button>
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
          <KPI label="In progress" value={productionActive.length} sub="Jobs on the production floor" />
          <KPI label="Fulfillment queue" value={fulfillmentSales.length} sub="Sales pending ship/deliver" />
          <KPI
            label="Ready printers"
            value={readyPrinters.length}
            sub={
              attentionPrinters.length > 0
                ? `${attentionPrinters.length} printer${attentionPrinters.length === 1 ? '' : 's'} need attention`
                : 'Idle, available for assignment'
            }
            tone={readyPrinters.length === 0 ? 'warning' : attentionPrinters.length > 0 ? 'warning' : 'default'}
          />
        </KPIStrip>
      </PageHeader>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          {/* Production queue */}
          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Production queue</h2>
              <Tabs value={queueFilter} onValueChange={(v) => setQueueFilter(v as QueueFilter)}>
                <TabsList>
                  <TabsTrigger value="all">
                    All <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">{jobs.length}</span>
                  </TabsTrigger>
                  <TabsTrigger value="needs-assignment">
                    Needs assignment
                    <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">
                      {jobsNeedingAssignment.length}
                    </span>
                  </TabsTrigger>
                  <TabsTrigger value="in-progress">
                    In progress
                    <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">
                      {productionActive.length}
                    </span>
                  </TabsTrigger>
                  <TabsTrigger value="draft">
                    Draft
                    <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">{draftJobs.length}</span>
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            <DataTable<Job>
              data={visibleJobs}
              columns={jobColumns}
              rowKey={(j) => j.id}
              onRowClick={(j) => navigate(`/orders/jobs/${j.id}`)}
              loading={jobsLoading || printersLoading}
              emptyState={
                queueFilter === 'needs-assignment'
                  ? 'No jobs waiting for a printer assignment.'
                  : queueFilter === 'in-progress'
                    ? 'No jobs currently on the production floor.'
                    : queueFilter === 'draft'
                      ? 'No drafts in the queue.'
                      : 'No recent jobs yet.'
              }
              toolbar={<TableToolbar total={visibleJobs.length} />}
            />
          </section>

          {/* Fulfillment queue */}
          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Fulfillment queue</h2>
              <Button asChild variant="outline" size="sm">
                <Link to="/sell/sales">
                  Open sales inbox <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </div>
            <DataTable<SaleListItem>
              data={fulfillmentSales.slice(0, 10)}
              columns={saleColumns}
              rowKey={(s) => s.id}
              onRowClick={(s) => navigate(`/sell/sales/${s.id}`)}
              loading={salesLoading}
              emptyState="No pending or paid sales in the current window."
              toolbar={<TableToolbar total={fulfillmentSales.length} />}
            />
          </section>
        </div>

        {/* Side rail */}
        <aside className="space-y-4">
          <section className="rounded-md border border-border bg-card p-4 shadow-xs">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                <h2 className="text-sm font-semibold">Top customers</h2>
              </div>
              <Link to="/orders/customers" className="text-xs text-primary no-underline hover:underline">
                Open
              </Link>
            </div>
            {topCustomers.length === 0 ? (
              <p className="text-sm text-muted-foreground">No customer activity yet.</p>
            ) : (
              <ul className="space-y-2">
                {topCustomers.map((customer) => (
                  <li
                    key={customer.id}
                    className="flex items-center justify-between gap-3 rounded-sm px-1 py-1"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{customer.name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {customer.email || customer.phone || 'No contact info'}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-sm font-semibold tabular-nums text-foreground">{customer.job_count}</p>
                      <p className="text-xs text-muted-foreground">jobs</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {attentionPrinters.length > 0 ? (
            <section className="rounded-md border border-amber-300/60 bg-amber-50/80 p-4 dark:border-amber-500/30 dark:bg-amber-500/10">
              <div className="mb-2 flex items-center gap-2">
                <TriangleAlert className="h-4 w-4 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                <h2 className="text-sm font-semibold text-amber-800 dark:text-amber-300">Printers need attention</h2>
              </div>
              <ul className="space-y-1 text-sm">
                {attentionPrinters.slice(0, 6).map((printer) => (
                  <li key={printer.id} className="flex items-center justify-between gap-3">
                    <Link
                      to={`/print-floor/printers/${printer.id}`}
                      className="truncate text-foreground no-underline hover:underline"
                    >
                      {printer.name}
                    </Link>
                    <StatusBadge tone={defaultStatusTone(printer.monitor_status || printer.status)} hideDot>
                      {(printer.monitor_status || printer.status).replace('_', ' ')}
                    </StatusBadge>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
