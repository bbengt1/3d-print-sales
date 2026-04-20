import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '@/components/ui/Button';

describe('Button', () => {
  it('renders with default variant classes', () => {
    render(<Button>Save</Button>);
    const btn = screen.getByRole('button', { name: 'Save' });
    expect(btn.className).toContain('bg-primary');
    expect(btn.className).toContain('h-9');
  });

  it('applies a secondary variant', () => {
    render(<Button variant="secondary">Cancel</Button>);
    const btn = screen.getByRole('button', { name: 'Cancel' });
    expect(btn.className).toContain('bg-secondary');
    expect(btn.className).not.toContain('bg-primary');
  });

  it('applies destructive variant', () => {
    render(<Button variant="destructive">Delete</Button>);
    const btn = screen.getByRole('button', { name: 'Delete' });
    expect(btn.className).toContain('bg-destructive');
  });

  it('applies outline + ghost + link variants', () => {
    render(
      <>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="link">Link</Button>
      </>,
    );
    expect(screen.getByRole('button', { name: 'Outline' }).className).toContain('border');
    expect(screen.getByRole('button', { name: 'Ghost' }).className).toContain('hover:bg-muted');
    expect(screen.getByRole('button', { name: 'Link' }).className).toContain('underline-offset-4');
  });

  it('sizes: sm, md, lg, icon', () => {
    render(
      <>
        <Button size="sm">S</Button>
        <Button size="md">M</Button>
        <Button size="lg">L</Button>
        <Button size="icon" aria-label="icon">Ø</Button>
      </>,
    );
    expect(screen.getByRole('button', { name: 'S' }).className).toContain('h-8');
    expect(screen.getByRole('button', { name: 'M' }).className).toContain('h-9');
    expect(screen.getByRole('button', { name: 'L' }).className).toContain('h-10');
    expect(screen.getByRole('button', { name: 'icon' }).className).toContain('w-9');
  });

  it('disabled prop disables the button and prevents clicks', () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Off
      </Button>,
    );
    const btn = screen.getByRole('button', { name: 'Off' });
    expect(btn.hasAttribute('disabled')).toBe(true);
    fireEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('fires onClick when enabled', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('asChild renders the child element with button styling', () => {
    render(
      <Button asChild>
        <a href="/somewhere">Link-as-button</a>
      </Button>,
    );
    const link = screen.getByRole('link', { name: 'Link-as-button' });
    expect(link.getAttribute('href')).toBe('/somewhere');
    expect(link.className).toContain('bg-primary');
  });
});
