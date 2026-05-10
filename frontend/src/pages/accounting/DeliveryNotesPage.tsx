import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
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

interface DN {
  id: string;
  delivery_number: string;
  invoice_id: string | null;
  customer_id: string | null;
  customer_name: string | null;
  issued_on: string;
  shipped_on: string | null;
  tracking_number: string | null;
  status: string;
}

interface LineDraft { description: string; quantity: string; notes: string }

const empty = {
  customer_name: '',
  invoice_id: '',
  issued_on: new Date().toISOString().slice(0, 10),
  tracking_number: '',
  lines: [{ description: '', quantity: '1', notes: '' }] as LineDraft[],
};

export default function DeliveryNotesPage() {
  const qc = useQueryClient();
  const list = useListQuery<DN>({ resource: 'delivery-notes' });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const setLine = (i: number, p: Partial<LineDraft>) => setForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, ...p } : l)) }));

  const save = async () => {
    if (!form.customer_name && !form.invoice_id) return toast.error('Customer name or invoice ID required');
    setSaving(true);
    try {
      await api.post('/delivery-notes', {
        invoice_id: form.invoice_id || null,
        customer_name: form.customer_name || null,
        issued_on: form.issued_on,
        tracking_number: form.tracking_number || null,
        lines: form.lines.map((l) => ({ description: l.description, quantity: l.quantity, notes: l.notes || null })),
      });
      toast.success('Delivery note created');
      qc.invalidateQueries({ queryKey: ['delivery-notes'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const setStatus = async (r: DN, status: string) => {
    try {
      await api.patch(`/delivery-notes/${r.id}`, { status });
      toast.success(status);
      qc.invalidateQueries({ queryKey: ['delivery-notes'] });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const cols: Column<DN>[] = [
    { key: 'n', header: 'DN #', cell: (r) => <span className="font-medium">{r.delivery_number}</span> },
    { key: 'c', header: 'Customer', cell: (r) => r.customer_name || '—' },
    { key: 'd', header: 'Issued', cell: (r) => r.issued_on },
    { key: 'tk', header: 'Tracking', cell: (r) => r.tracking_number || '—' },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
    { key: 'a', header: '', width: '180px', cell: (r) => (
      <div className="flex justify-end gap-1">
        {r.status === 'draft' && <Button size="sm" variant="outline" onClick={() => setStatus(r, 'shipped')}>Ship</Button>}
        {r.status === 'shipped' && <Button size="sm" variant="outline" onClick={() => setStatus(r, 'delivered')}>Deliver</Button>}
      </div>
    ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Delivery notes" description="Dispatch documents (DLV-…). No GL impact." actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New DN</Button>} />
      <DataTable data={list.data} columns={cols} rowKey={(r) => r.id} loading={list.isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New delivery note</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Customer name</Label><Input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} /></div>
              <div><Label>Invoice ID (opt.)</Label><Input value={form.invoice_id} onChange={(e) => setForm({ ...form, invoice_id: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Issued</Label><Input type="date" value={form.issued_on} onChange={(e) => setForm({ ...form, issued_on: e.target.value })} /></div>
              <div><Label>Tracking #</Label><Input value={form.tracking_number} onChange={(e) => setForm({ ...form, tracking_number: e.target.value })} /></div>
            </div>
            <div className="space-y-2">
              <Label>Lines</Label>
              {form.lines.map((line, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <Input className="col-span-9" placeholder="Description" value={line.description} onChange={(e) => setLine(i, { description: e.target.value })} />
                  <Input className="col-span-3" placeholder="Qty" value={line.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} />
                </div>
              ))}
              <Button size="sm" variant="outline" onClick={() => setForm((f) => ({ ...f, lines: [...f.lines, { description: '', quantity: '1', notes: '' }] }))}>+ Add line</Button>
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
