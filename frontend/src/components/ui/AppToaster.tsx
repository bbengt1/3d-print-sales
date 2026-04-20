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
          success: 'border-emerald-300/60 bg-emerald-50/90 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200',
          error: 'border-destructive/40 bg-destructive/10 text-destructive',
          warning: 'border-amber-300/60 bg-amber-50/90 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200',
          info: 'border-sky-300/60 bg-sky-50/90 text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200',
        },
      }}
    />
  );
}
