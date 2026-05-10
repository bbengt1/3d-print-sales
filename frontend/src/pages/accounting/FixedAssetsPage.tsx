import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { getApiErrorMessage } from '@/lib/apiError';

interface FA {
  id: string;
  name: string;
  acquired_on: string;
  cost: number;
  salvage_value: number;
  useful_life_months: number;
  method: string;
  status: string;
  accumulated_depreciation: number;
}

const empty = { name: '', acquired_on: new Date().toISOString().slice(0, 10), cost: '0', salvage_value: '0', useful_life_months: '60', method: 'straight_line' };

export default function FixedAssetsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<FA[]>({ queryKey: ['fixed-assets'], queryFn: () => api.get('/fixed-assets').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [throughDate, setThroughDate] = useState(new Date().toISOString().slice(0, 10));

  const save = async () => {
    if (!form.name) return toast.error('Name required');
    setSaving(true);
    try {
      await api.post('/fixed-assets', form);
      toast.success('Asset registered');
      qc.invalidateQueries({ queryKey: ['fixed-assets'] });
      setOpen(false); setForm(empty);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
    finally { setSaving(false); }
  };

  const post = async () => {
    try {
      await api.post('/fixed-assets/post-depreciation', { through_date: throughDate });
      toast.success('Depreciation posted');
      qc.invalidateQueries({ queryKey: ['fixed-assets'] });
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const cols: Column<FA>[] = [
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'd', header: 'Acquired', cell: (r) => r.acquired_on },
    { key: 'c', header: 'Cost', numeric: true, cell: (r) => `$${Number(r.cost).toFixed(2)}` },
    { key: 'a', header: 'Acc. dep.', numeric: true, cell: (r) => `$${Number(r.accumulated_depreciation).toFixed(2)}` },
    { key: 'm', header: 'Method', cell: (r) => r.method },
    { key: 'l', header: 'Life (mo)', numeric: true, cell: (r) => r.useful_life_months },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Fixed assets" description="Capital assets with depreciation schedule" actions={<Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />Register asset</Button>} />
      <div className="flex items-end gap-2 rounded-lg border bg-card p-3">
        <div><Label>Post depreciation through</Label><Input type="date" value={throughDate} onChange={(e) => setThroughDate(e.target.value)} /></div>
        <Button onClick={post}><RefreshCw className="mr-2 h-4 w-4" />Run</Button>
      </div>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Register fixed asset</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Acquired on</Label><Input type="date" value={form.acquired_on} onChange={(e) => setForm({ ...form, acquired_on: e.target.value })} /></div>
              <div><Label>Cost</Label><Input type="number" step="0.01" value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label>Salvage</Label><Input type="number" step="0.01" value={form.salvage_value} onChange={(e) => setForm({ ...form, salvage_value: e.target.value })} /></div>
              <div><Label>Life (months)</Label><Input type="number" value={form.useful_life_months} onChange={(e) => setForm({ ...form, useful_life_months: e.target.value })} /></div>
              <div>
                <Label>Method</Label>
                <select className="mt-1 block w-full rounded-md border bg-background px-2 py-2 text-sm" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>
                  <option value="straight_line">straight_line</option>
                  <option value="double_declining">double_declining</option>
                </select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Register'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
