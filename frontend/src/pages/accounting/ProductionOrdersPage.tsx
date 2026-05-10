import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, CheckCircle2, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { getApiErrorMessage } from '@/lib/apiError';

interface PO {
  id: string;
  order_number: string;
  product_id: string;
  product_name: string | null;
  planned_quantity: number;
  status: string;
  planned_on: string;
  closed_on: string | null;
}

const empty = { product_id: '', planned_quantity: '1', planned_on: new Date().toISOString().slice(0, 10) };

export default function ProductionOrdersPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<PO[]>({ queryKey: ['production-orders'], queryFn: () => api.get('/production-orders').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!form.product_id) return toast.error('Product ID required');
    setSaving(true);
    try {
      await api.post('/production-orders', { ...form, planned_quantity: Number(form.planned_quantity) });
      toast.success('Created');
      qc.invalidateQueries({ queryKey: ['production-orders'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const action = async (id: string, verb: string) => {
    try {
      await api.post(`/production-orders/${id}/${verb}`);
      toast.success(verb);
      qc.invalidateQueries({ queryKey: ['production-orders'] });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const cols: Column<PO>[] = [
    { key: 'n', header: 'Order #', cell: (r) => <span className="font-medium">{r.order_number}</span> },
    { key: 'p', header: 'Product', cell: (r) => r.product_name || r.product_id },
    { key: 'q', header: 'Qty', numeric: true, cell: (r) => r.planned_quantity },
    { key: 'd', header: 'Planned', cell: (r) => r.planned_on },
    { key: 'c', header: 'Closed', cell: (r) => r.closed_on || '—' },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
    { key: 'a', header: '', width: '160px', cell: (r) => (
      <div className="flex justify-end gap-1">
        {r.status === 'planned' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'close')}><CheckCircle2 className="mr-1 h-3.5 w-3.5" />Close</Button>}
        {r.status === 'planned' && <Button size="sm" variant="ghost" onClick={() => action(r.id, 'cancel')}><X className="h-3.5 w-3.5" /></Button>}
      </div>
    ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Production orders" description="Plan production runs; closing FIFO-consumes materials and creates a finished-goods layer." actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New order</Button>} />
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New production order</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Product ID</Label><Input value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Quantity</Label><Input type="number" min={1} value={form.planned_quantity} onChange={(e) => setForm({ ...form, planned_quantity: e.target.value })} /></div>
              <div><Label>Planned on</Label><Input type="date" value={form.planned_on} onChange={(e) => setForm({ ...form, planned_on: e.target.value })} /></div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Create'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
