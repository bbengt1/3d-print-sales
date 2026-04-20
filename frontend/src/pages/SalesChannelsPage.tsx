import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import PageHeader from '@/components/layout/PageHeader';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';
import StatusBadge from '@/components/data/StatusBadge';
import DataTable, { type Column } from '@/components/data/DataTable';
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
    <div className="space-y-6">
      <PageHeader
        title="Sales Channels"
        description="Manage platforms, fees, and active status for every place you sell."
        actions={
          <Button onClick={openNew}>
            <Plus className="h-4 w-4" /> Add channel
          </Button>
        }
      />

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

      <SalesChannelsTable
        channels={channels || []}
        isLoading={isLoading}
        onEdit={openEdit}
        onToggleActive={toggleActive}
      />
    </div>
  );
}

interface SalesChannelsTableProps {
  channels: SalesChannel[];
  isLoading: boolean;
  onEdit: (ch: SalesChannel) => void;
  onToggleActive: (ch: SalesChannel) => void;
}

function SalesChannelsTable({ channels, isLoading, onEdit, onToggleActive }: SalesChannelsTableProps) {
  const columns: Column<SalesChannel>[] = [
    {
      key: 'name',
      header: 'Name',
      cell: (ch) => <span className="font-medium">{ch.name}</span>,
    },
    {
      key: 'platform_fee_pct',
      header: 'Platform Fee %',
      numeric: true,
      cell: (ch) => <span className="tabular-nums">{Number(ch.platform_fee_pct).toFixed(1)}%</span>,
    },
    {
      key: 'fixed_fee',
      header: 'Fixed Fee',
      numeric: true,
      cell: (ch) => <span className="tabular-nums">${Number(ch.fixed_fee).toFixed(2)}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      cell: (ch) => (
        <button
          type="button"
          onClick={() => onToggleActive(ch)}
          aria-label={ch.is_active ? `Deactivate ${ch.name}` : `Activate ${ch.name}`}
        >
          <StatusBadge tone={ch.is_active ? 'success' : 'destructive'}>
            {ch.is_active ? 'Active' : 'Inactive'}
          </StatusBadge>
        </button>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '96px',
      cell: (ch) => (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => onEdit(ch)}
              aria-label={`Edit ${ch.name}`}
            >
              <Edit className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Edit</TooltipContent>
        </Tooltip>
      ),
    },
  ];

  return (
    <DataTable<SalesChannel>
      data={channels}
      columns={columns}
      rowKey={(ch) => ch.id}
      loading={isLoading}
      emptyState="No sales channels"
    />
  );
}
