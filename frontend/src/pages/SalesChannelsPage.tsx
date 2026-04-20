import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { SkeletonTable } from '@/components/ui/Skeleton';
import EmptyState from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import StatusBadge from '@/components/data/StatusBadge';
import type { SalesChannel } from '@/types';

const emptyForm = { name: '', platform_fee_pct: 0, fixed_fee: 0, is_active: true };

export default function SalesChannelsPage() {
  const queryClient = useQueryClient();
  const { data: channels, isLoading } = useQuery<SalesChannel[]>({
    queryKey: ['sales-channels'],
    queryFn: () => api.get('/sales/channels').then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const openNew = () => { setForm(emptyForm); setEditing('new'); };
  const openEdit = (ch: SalesChannel) => {
    setForm({
      name: ch.name,
      platform_fee_pct: Number(ch.platform_fee_pct),
      fixed_fee: Number(ch.fixed_fee),
      is_active: ch.is_active,
    });
    setEditing(ch.id);
  };
  const close = () => setEditing(null);

  const save = async () => {
    if (!form.name.trim()) { toast.error('Name is required'); return; }
    setSaving(true);
    try {
      if (editing === 'new') {
        await api.post('/sales/channels', form);
        toast.success('Channel created');
      } else {
        await api.put(`/sales/channels/${editing}`, form);
        toast.success('Channel updated');
      }
      queryClient.invalidateQueries({ queryKey: ['sales-channels'] });
      close();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (ch: SalesChannel) => {
    try {
      if (ch.is_active) {
        await api.delete(`/sales/channels/${ch.id}`);
        toast.success(`${ch.name} deactivated`);
      } else {
        await api.put(`/sales/channels/${ch.id}`, { is_active: true });
        toast.success(`${ch.name} activated`);
      }
      queryClient.invalidateQueries({ queryKey: ['sales-channels'] });
    } catch {
      toast.error('Failed to update');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Sales Channels</h1>
        <Button onClick={openNew}>
          <Plus className="h-4 w-4" /> Add Channel
        </Button>
      </div>

      <Dialog open={editing !== null} onOpenChange={(o) => !o && close()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing === 'new' ? 'Add channel' : 'Edit channel'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="channel-name">Name *</Label>
              <Input id="channel-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="channel-fee-pct">Platform fee %</Label>
                <Input
                  id="channel-fee-pct"
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  value={form.platform_fee_pct}
                  onChange={(e) => setForm({ ...form, platform_fee_pct: Number(e.target.value) })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="channel-fixed-fee">Fixed fee ($)</Label>
                <Input
                  id="channel-fixed-fee"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.fixed_fee}
                  onChange={(e) => setForm({ ...form, fixed_fee: Number(e.target.value) })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={close}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isLoading ? (
        <SkeletonTable rows={4} cols={5} />
      ) : !channels?.length ? (
        <EmptyState
          icon="default"
          title="No sales channels"
          description="Add a sales channel to track platform fees."
          action={
            <Button onClick={openNew}>
              <Plus className="h-4 w-4" /> Add Channel
            </Button>
          }
        />
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium text-right">Platform Fee %</th>
                <th className="px-4 py-3 font-medium text-right">Fixed Fee</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {channels.map((ch) => (
                <tr key={ch.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{ch.name}</td>
                  <td className="px-4 py-3 text-right">{Number(ch.platform_fee_pct).toFixed(1)}%</td>
                  <td className="px-4 py-3 text-right">${Number(ch.fixed_fee).toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleActive(ch)} className="cursor-pointer">
                      <StatusBadge tone={ch.is_active ? 'success' : 'destructive'}>
                        {ch.is_active ? 'Active' : 'Inactive'}
                      </StatusBadge>
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => openEdit(ch)} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground cursor-pointer" title="Edit">
                      <Edit className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
