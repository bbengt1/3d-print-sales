import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatusBadge, { defaultStatusTone } from '@/components/data/StatusBadge';

describe('StatusBadge', () => {
  it('renders the label', () => {
    render(<StatusBadge tone="success">Paid</StatusBadge>);
    expect(screen.getByText('Paid')).toBeTruthy();
  });

  it('renders a leading dot by default', () => {
    const { container } = render(<StatusBadge tone="warning">Pending</StatusBadge>);
    // Dot is a span with rounded-full
    expect(container.querySelector('span.rounded-full')).not.toBeNull();
  });

  it('can hide the leading dot', () => {
    const { container } = render(
      <StatusBadge tone="warning" hideDot>
        Pending
      </StatusBadge>,
    );
    expect(container.querySelector('span.rounded-full')).toBeNull();
  });
});

describe('defaultStatusTone', () => {
  it('maps known statuses to expected tones', () => {
    expect(defaultStatusTone('paid')).toBe('success');
    expect(defaultStatusTone('pending')).toBe('warning');
    expect(defaultStatusTone('refunded')).toBe('destructive');
    expect(defaultStatusTone('cancelled')).toBe('destructive');
    expect(defaultStatusTone('shipped')).toBe('info');
    expect(defaultStatusTone('idle')).toBe('info');
  });

  it('maps unknown statuses to neutral', () => {
    expect(defaultStatusTone('widget-status')).toBe('neutral');
    expect(defaultStatusTone('')).toBe('neutral');
  });

  it('is case-insensitive', () => {
    expect(defaultStatusTone('PAID')).toBe('success');
    expect(defaultStatusTone('Draft')).toBe('warning');
  });
});
