import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge } from '@/components/ui/Badge';

describe('Badge', () => {
  it('renders default variant with primary bg', () => {
    render(<Badge>New</Badge>);
    const el = screen.getByText('New');
    expect(el.className).toContain('bg-primary');
  });

  it('supports secondary / destructive / outline / muted', () => {
    render(
      <>
        <Badge variant="secondary">S</Badge>
        <Badge variant="destructive">D</Badge>
        <Badge variant="outline">O</Badge>
        <Badge variant="muted">M</Badge>
      </>,
    );
    expect(screen.getByText('S').className).toContain('bg-secondary');
    expect(screen.getByText('D').className).toContain('bg-destructive');
    expect(screen.getByText('O').className).toContain('border-border');
    expect(screen.getByText('M').className).toContain('bg-muted');
  });

  it('forwards className', () => {
    render(<Badge className="ml-4">Tag</Badge>);
    expect(screen.getByText('Tag').className).toContain('ml-4');
  });
});
