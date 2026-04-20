import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/Dialog';

describe('Dialog', () => {
  it('opens when the trigger is clicked and renders title + description', () => {
    render(
      <Dialog>
        <DialogTrigger>Open</DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Are you sure?</DialogTitle>
            <DialogDescription>This will deactivate the printer.</DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>,
    );

    expect(screen.queryByText('Are you sure?')).toBeNull();
    fireEvent.click(screen.getByText('Open'));
    expect(screen.getByText('Are you sure?')).toBeTruthy();
    expect(screen.getByText('This will deactivate the printer.')).toBeTruthy();
  });

  it('exposes a close button with accessible label', () => {
    render(
      <Dialog defaultOpen>
        <DialogContent>
          <DialogTitle>Test</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByLabelText('Close dialog')).toBeTruthy();
  });

  it('does not render the built-in close button when hideClose is set', () => {
    render(
      <Dialog defaultOpen>
        <DialogContent hideClose>
          <DialogTitle>Test</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.queryByLabelText('Close dialog')).toBeNull();
  });

  it('fires onOpenChange(false) when the close button is clicked', () => {
    const onOpenChange = vi.fn();
    render(
      <Dialog open onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogTitle>Test</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    fireEvent.click(screen.getByLabelText('Close dialog'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
