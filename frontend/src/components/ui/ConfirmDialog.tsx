import { useState, type ReactNode } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

export type ConfirmDialogTone = 'default' | 'destructive';

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Optional plain-language explanation of what will happen. */
  description?: ReactNode;
  /** Label on the confirm button. Defaults to "Confirm". */
  confirmLabel?: string;
  /** Label on the cancel button. Defaults to "Cancel". */
  cancelLabel?: string;
  /** `destructive` renders the confirm button in the destructive variant (red). */
  tone?: ConfirmDialogTone;
  /**
   * Called when the user clicks the confirm button. If it returns a Promise, the
   * confirm button shows a pending state until it resolves.
   */
  onConfirm: () => void | Promise<void>;
  /** Close dialog automatically when onConfirm resolves. Default true. */
  closeOnConfirm?: boolean;
  /** Replace the default confirm button label when pending. */
  pendingLabel?: string;
  /** Additional classes on the DialogContent (e.g. max-w override). */
  className?: string;
}

/**
 * Styled replacement for `window.confirm()`. Built on top of Radix Dialog so it
 * inherits focus-trap, ESC-to-close, and overlay click-to-close for free.
 *
 * ```tsx
 * const [open, setOpen] = useState(false);
 *
 * <Button variant="outline" onClick={() => setOpen(true)}>Delete</Button>
 * <ConfirmDialog
 *   open={open}
 *   onOpenChange={setOpen}
 *   title="Delete customer?"
 *   description={`${customer.name} will be removed. This cannot be undone.`}
 *   confirmLabel="Delete"
 *   tone="destructive"
 *   onConfirm={async () => { await api.delete(`/customers/${customer.id}`); }}
 * />
 * ```
 */
export default function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'default',
  onConfirm,
  closeOnConfirm = true,
  pendingLabel,
  className,
}: ConfirmDialogProps) {
  const [pending, setPending] = useState(false);

  const handleConfirm = async () => {
    setPending(true);
    try {
      await onConfirm();
      if (closeOnConfirm) onOpenChange(false);
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent className={cn('max-w-md', className)}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === 'destructive' ? 'destructive' : 'primary'}
            onClick={handleConfirm}
            disabled={pending}
          >
            {pending ? pendingLabel || `${confirmLabel}…` : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
