import { forwardRef, useId, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
  /**
   * Inline validation message. When set, the textarea renders with
   * destructive styling, `aria-invalid="true"`, and a below-textarea
   * error paragraph wired via `aria-describedby`. Overrides `invalid`.
   */
  error?: string | null | false;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid = false, error, id: providedId, 'aria-describedby': describedBy, ...props },
  ref,
) {
  const generatedId = useId();
  const id = providedId ?? generatedId;
  const errorId = error ? `${id}-error` : undefined;
  const isInvalid = Boolean(error) || invalid;

  const textareaEl = (
    <textarea
      ref={ref}
      id={id}
      aria-invalid={isInvalid || undefined}
      aria-describedby={cn(describedBy, errorId) || undefined}
      className={cn(
        'flex min-h-[72px] w-full rounded-md border bg-background px-3 py-2 text-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
        isInvalid ? 'border-destructive focus-visible:ring-destructive' : 'border-input',
        className,
      )}
      {...props}
    />
  );

  if (!error) return textareaEl;

  return (
    <div className="space-y-1">
      {textareaEl}
      <p id={errorId} className="text-xs text-destructive">
        {error}
      </p>
    </div>
  );
});
