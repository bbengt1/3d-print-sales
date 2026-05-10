import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus, Mail } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Textarea } from '@/components/ui/Textarea';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { useListQuery } from '@/hooks/useListQuery';
import { getApiErrorMessage } from '@/lib/apiError';

interface Invoice {
  id: string;
  invoice_number: string;
  customer_id: string | null;
  customer_name: string | null;
  issue_date: string;
  due_date: string | null;
  total_due: number;
  amount_paid: number;
  balance_due: number;
  status: string;
}

interface LineDraft { description: string; quantity: number; unit_price: string }

const emptyForm = {
  customer_name: '',
  issue_date: new Date().toISOString().slice(0, 10),
  due_date: '',
  notes: '',
  tax_amount: '0',
  shipping_amount: '0',
  lines: [{ description: '', quantity: 1, unit_price: '0' }] as LineDraft[],
};

export default function InvoicesPage() {
  const qc = useQueryClient();
  const list = useListQuery<Invoice>({ resource: 'invoices' });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [emailing, setEmailing] = useState<Invoice | null>(null);
  const [emailTo, setEmailTo] = useState('');
  const [emailSending, setEmailSending] = useState(false);

  const setLine = (i: number, patch: Partial<LineDraft>) => {
    setForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)) }));
  };
  const addLine = () => setForm((f) => ({ ...f, lines: [...f.lines, { description: '', quantity: 1, unit_price: '0' }] }));
  const removeLine = (i: number) => setForm((f) => ({ ...f, lines: f.lines.filter((_, idx) => idx !== i) }));

  const save = async () => {
    if (!form.customer_name) { toast.error('Customer name required'); return; }
    if (form.lines.length === 0 || !form.lines[0].description) { toast.error('At least one line required'); return; }
    setSaving(true);
    try {
      await api.post('/invoices', {
        customer_name: form.customer_name,
        issue_date: form.issue_date,
        due_date: form.due_date || null,
        notes: form.notes || null,
        tax_amount: form.tax_amount,
        shipping_amount: form.shipping_amount,
        lines: form.lines.map((l) => ({ description: l.description, quantity: l.quantity, unit_price: l.unit_price })),
      });
      toast.success('Invoice created');
      qc.invalidateQueries({ queryKey: ['invoices'] });
      setOpen(false);
      setForm(emptyForm);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed to create')); }
    finally { setSaving(false); }
  };

  const sendEmail = async () => {
    if (!emailing) return;
    setEmailSending(true);
    try {
      await api.post(`/invoices/${emailing.id}/send-email`, { to_email: emailTo || null });
      toast.success('Email queued');
      setEmailing(null);
      setEmailTo('');
    } catch (err) { toast.error(getApiErrorMessage(err, 'Email failed')); }
    finally { setEmailSending(false); }
  };

  const columns: Column<Invoice>[] = [
    { key: 'number', header: 'Invoice #', cell: (r) => <span className="font-medium">{r.invoice_number}</span> },
    { key: 'customer', header: 'Customer', cell: (r) => r.customer_name || '—' },
    { key: 'issue_date', header: 'Issued', cell: (r) => r.issue_date },
    { key: 'due_date', header: 'Due', cell: (r) => r.due_date || '—' },
    { key: 'total', header: 'Total', numeric: true, cell: (r) => `$${Number(r.total_due).toFixed(2)}` },
    { key: 'balance', header: 'Balance', numeric: true, cell: (r) => `$${Number(r.balance_due).toFixed(2)}` },
    { key: 'status', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
    {
      key: 'actions', header: '', width: '100px',
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="icon" variant="ghost" onClick={() => { setEmailing(r); setEmailTo(''); }} aria-label="Email">
            <Mail className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Invoices"
        description="Customer-facing invoices with email send"
        actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New invoice</Button>}
      />
      <DataTable data={list.data} columns={columns} rowKey={(r) => r.id} loading={list.isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>New invoice</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Customer name</Label><Input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Issue date</Label><Input type="date" value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} /></div>
              <div><Label>Due date</Label><Input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></div>
            </div>
            <div className="space-y-2">
              <Label>Lines</Label>
              {form.lines.map((line, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <Input className="col-span-6" placeholder="Description" value={line.description} onChange={(e) => setLine(i, { description: e.target.value })} />
                  <Input className="col-span-2" type="number" min={1} value={line.quantity} onChange={(e) => setLine(i, { quantity: Number(e.target.value) })} />
                  <Input className="col-span-3" type="number" step="0.01" value={line.unit_price} onChange={(e) => setLine(i, { unit_price: e.target.value })} />
                  <Button variant="ghost" size="sm" className="col-span-1" onClick={() => removeLine(i)} disabled={form.lines.length === 1}>×</Button>
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={addLine}>+ Add line</Button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Tax</Label><Input type="number" step="0.01" value={form.tax_amount} onChange={(e) => setForm({ ...form, tax_amount: e.target.value })} /></div>
              <div><Label>Shipping</Label><Input type="number" step="0.01" value={form.shipping_amount} onChange={(e) => setForm({ ...form, shipping_amount: e.target.value })} /></div>
            </div>
            <div><Label>Notes</Label><Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Create'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(emailing)} onOpenChange={(o) => !o && setEmailing(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Email invoice {emailing?.invoice_number}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>To (override)</Label><Input value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="leave blank to use customer email" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailing(null)}>Cancel</Button>
            <Button onClick={sendEmail} disabled={emailSending}>{emailSending ? 'Sending…' : 'Send'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
