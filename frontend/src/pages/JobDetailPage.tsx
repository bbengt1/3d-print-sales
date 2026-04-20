import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Edit, Calendar, User, Package, Printer, Copy } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';
import Breadcrumbs from '@/components/ui/Breadcrumbs';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { formatCurrency, formatPercent } from '@/lib/utils';
import type { Job } from '@/types';

function CostRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between py-2 border-b border-border last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{formatCurrency(value)}</span>
    </div>
  );
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [duplicating, setDuplicating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: job, isLoading } = useQuery<Job>({
    queryKey: ['job', id],
    queryFn: () => api.get(`/jobs/${id}`).then((r) => r.data),
  });

  const handleDelete = async () => {
    try {
      await api.delete(`/jobs/${id}`);
      toast.success('Job deleted');
      navigate('/orders/jobs');
    } catch {
      toast.error('Failed to delete job');
    }
  };

  const handleDuplicate = async () => {
    setDuplicating(true);
    try {
      const { data } = await api.post(`/jobs/${id}/duplicate`);
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      toast.success('Job copied to draft successfully');
      navigate(`/orders/jobs/${data.id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to copy job');
    } finally {
      setDuplicating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonCard key={i} rows={2} />
        ))}
      </div>
    );
  }

  if (!job) return <p className="text-muted-foreground">Job not found</p>;

  const marginPct = job.total_revenue > 0 ? (job.net_profit / job.total_revenue) * 100 : 0;

  return (
    <div className="space-y-6">
      <Breadcrumbs
        items={[
          { to: '/orders/jobs', label: 'Jobs' },
          { label: job.job_number },
        ]}
      />
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button asChild variant="ghost" size="icon" className="h-8 w-8">
                <Link to="/orders/jobs" aria-label="Back to jobs">
                  <ArrowLeft className="h-4 w-4" />
                </Link>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Back to jobs</TooltipContent>
          </Tooltip>
          <div>
            <h1 className="text-2xl font-semibold">{job.job_number}</h1>
            <p className="text-muted-foreground text-sm">{job.product_name}</p>
          </div>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
            {job.status}
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleDuplicate} disabled={duplicating}>
            <Copy className="h-4 w-4" /> {duplicating ? 'Copying...' : 'Copy to New Job'}
          </Button>
          <Button asChild variant="outline">
            <Link to={`/orders/jobs/${id}/edit`}>
              <Edit className="h-4 w-4" /> Edit
            </Link>
          </Button>
          <Button
            variant="outline"
            onClick={() => setConfirmDelete(true)}
            className="border-destructive/30 text-destructive hover:bg-destructive/10"
          >
            Delete
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete job?"
        description={`${job?.job_number ?? 'This job'} will be permanently removed. This cannot be undone.`}
        confirmLabel="Delete"
        tone="destructive"
        onConfirm={handleDelete}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-3">
          <Calendar className="w-5 h-5 text-muted-foreground" />
          <div><p className="text-xs text-muted-foreground">Date</p><p className="font-medium">{job.date}</p></div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-3">
          <User className="w-5 h-5 text-muted-foreground" />
          <div><p className="text-xs text-muted-foreground">Customer</p><p className="font-medium">{job.customer_name || '—'}</p></div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-3">
          <Package className="w-5 h-5 text-muted-foreground" />
          <div><p className="text-xs text-muted-foreground">Total Pieces</p><p className="font-medium">{job.total_pieces} ({job.qty_per_plate} x {job.num_plates} plates)</p></div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-3">
          <Printer className="w-5 h-5 text-muted-foreground" />
          <div><p className="text-xs text-muted-foreground">Print Time</p><p className="font-medium">{Number(job.print_time_per_plate_hrs).toFixed(1)}h x {job.num_plates} plates</p></div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-3">
          <Printer className="w-5 h-5 text-muted-foreground" />
          <div>
            <p className="text-xs text-muted-foreground">Assigned Printer</p>
            <p className="font-medium">{job.printer?.name || 'Unassigned'}</p>
            {job.printer && (
              <p className="text-xs text-muted-foreground">{job.printer.status}{job.printer.location ? ` · ${job.printer.location}` : ''}</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost Breakdown */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="text-base font-semibold mb-4">Cost Breakdown</h3>
          <CostRow label="Electricity" value={job.electricity_cost} />
          <CostRow label="Material" value={job.material_cost} />
          <CostRow label="Labor" value={job.labor_cost} />
          <CostRow label="Design" value={job.design_cost} />
          <CostRow label="Machine" value={job.machine_cost} />
          <CostRow label="Packaging" value={job.packaging_cost} />
          <CostRow label="Shipping" value={job.shipping_cost} />
          <CostRow label="Failure Buffer" value={job.failure_buffer} />
          <CostRow label="Overhead" value={job.overhead} />
          <div className="flex justify-between py-2 mt-2 border-t-2 border-border font-semibold">
            <span>Total Cost</span>
            <span>{formatCurrency(job.total_cost)}</span>
          </div>
          <div className="text-sm text-muted-foreground mt-1 text-right">
            {formatCurrency(job.cost_per_piece)} per piece
          </div>
        </div>

        {/* Pricing & Profit */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="text-base font-semibold mb-4">Pricing & Profit</h3>
          <div className="space-y-4">
            <div className="flex justify-between py-2 border-b border-border">
              <span className="text-muted-foreground">Target Margin</span>
              <span className="font-medium">{formatPercent(job.target_margin_pct)}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-border">
              <span className="text-muted-foreground">Price per Piece</span>
              <span className="font-medium">{formatCurrency(job.price_per_piece)}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-border">
              <span className="text-muted-foreground">Total Revenue</span>
              <span className="font-semibold text-lg">{formatCurrency(job.total_revenue)}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-border">
              <span className="text-muted-foreground">Platform Fees</span>
              <span className="font-medium text-destructive">-{formatCurrency(job.platform_fees)}</span>
            </div>
            <div className="flex justify-between py-2 mt-2 border-t-2 border-border">
              <span className="font-semibold">Net Profit</span>
              <span className={`font-semibold text-lg ${job.net_profit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}`}>
                {formatCurrency(job.net_profit)}
              </span>
            </div>
            <div className="text-sm text-muted-foreground text-right">
              {formatCurrency(job.profit_per_piece)} per piece &middot; {formatPercent(marginPct)} actual margin
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
