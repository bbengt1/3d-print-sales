import { Toaster as SonnerToaster } from 'sonner';
import { useTheme } from '@/hooks/useTheme';

/**
 * Thin wrapper around `sonner`'s Toaster that binds the theme to the app's
 * dark-mode toggle and styles toast surfaces with our design tokens
 * (bg-card / border-border / text-foreground + tone-specific borders).
 * Mount once at the app shell level.
 */
export default function AppToaster() {
  const { dark } = useTheme();

  return (
    <SonnerToaster
      theme={dark ? 'dark' : 'light'}
      position="top-right"
      closeButton
      toastOptions={{
        classNames: {
          toast:
            'group rounded-md border border-border bg-card text-foreground shadow-md text-sm',
          title: 'text-sm font-semibold text-foreground',
          description: 'text-xs text-muted-foreground',
          actionButton:
            'rounded-md bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:opacity-90',
          cancelButton:
            'rounded-md border border-border bg-card px-2 py-1 text-xs font-medium text-foreground hover:bg-muted',
          closeButton:
            'rounded-md border border-border bg-card text-muted-foreground hover:bg-muted',
          success: 'border-success-border bg-success-surface text-success dark:border-success/40 dark:bg-success/15 dark:text-success',
          error: 'border-destructive-border bg-destructive-surface text-destructive dark:border-destructive/40 dark:bg-destructive/15',
          warning: 'border-warning-border bg-warning-surface text-warning dark:border-warning/40 dark:bg-warning/15 dark:text-warning',
          info: 'border-info-border bg-info-surface text-info dark:border-info/40 dark:bg-info/15 dark:text-info',
        },
      }}
    />
  );
}
