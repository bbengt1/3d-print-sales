import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus, FileText, CheckCircle2, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { useListQuery } from '@/hooks/useListQuery';
import { getApiErrorMessage } from '@/lib/apiError';

interface PO {
  id: string;
  order_number: string;
  vendor_id: string | null;
  vendor_name: string | null;
  issue_date: string;
  total_amount: number;
  status: string;
}

interface LineDraft { description: string; quantity: string; unit_price: string }

const empty = { vendor_name: '', issue_date: new Date().toISOString().slice(0, 10), lines: [{ description: '', quantity: '1', unit_price: '0' }] as LineDraft[] };

export default function PurchaseOrdersPage() {
  const qc = useQueryClient();
  const list = useListQuery<PO>({ resource: 'purchase-orders' });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const setLine = (i: number, p: Partial<LineDraft>) => setForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, ...p } : l)) }));

  const save = async () => {
    if (!form.vendor_name) return toast.error('Vendor required');
    setSaving(true);
    try {
      await api.post('/purchase-orders', form);
      toast.success('Purchase order created');
      qc.invalidateQueries({ queryKey: ['purchase-orders'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const action = async (id: string, verb: string) => {
    try {
      await api.post(`/purchase-orders/${id}/${verb}`);
      toast.success(verb);
      qc.invalidateQueries({ queryKey: ['purchase-orders'] });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Action failed')); }
  };

  const cols: Column<PO>[] = [
    { key: 'n', header: 'Order #', cell: (r) => <span className="font-medium">{r.order_number}</span> },
    { key: 'v', header: 'Vendor', cell: (r) => r.vendor_name || '—' },
    { key: 'd', header: 'Issued', cell: (r) => r.issue_date },
    { key: 't', header: 'Total', numeric: true, cell: (r) => `$${Number(r.total_amount).toFixed(2)}` },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
    { key: 'a', header: '', width: '160px', cell: (r) => (
      <div className="flex justify-end gap-1">
        {r.status === 'draft' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'confirm')}><CheckCircle2 className="h-3.5 w-3.5" /></Button>}
        {r.status === 'confirmed' && <Button size="sm" variant="outline" onClick={() => action(r.id, 'create-bill')}><FileText className="mr-1 h-3.5 w-3.5" />Bill</Button>}
        {r.status !== 'fulfilled' && r.status !== 'cancelled' && <Button size="sm" variant="ghost" onClick={() => action(r.id, 'cancel')}><X className="h-3.5 w-3.5" /></Button>}
      </div>
    ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Purchase orders" description="Vendor commitments. Convert to bill when received." actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New PO</Button>} />
      <DataTable data={list.data} columns={cols} rowKey={(r) => r.id} loading={list.isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New purchase order</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Vendor name</Label><Input value={form.vendor_name} onChange={(e) => setForm({ ...form, vendor_name: e.target.value })} /></div>
            <div><Label>Issue date</Label><Input type="date" value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} /></div>
            <div className="space-y-2">
              <Label>Lines</Label>
              {form.lines.map((line, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <Input className="col-span-7" placeholder="Description" value={line.description} onChange={(e) => setLine(i, { description: e.target.value })} />
                  <Input className="col-span-2" value={line.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} />
                  <Input className="col-span-3" type="number" step="0.01" value={line.unit_price} onChange={(e) => setLine(i, { unit_price: e.target.value })} />
                </div>
              ))}
              <Button size="sm" variant="outline" onClick={() => setForm((f) => ({ ...f, lines: [...f.lines, { description: '', quantity: '1', unit_price: '0' }] }))}>+ Add line</Button>
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
