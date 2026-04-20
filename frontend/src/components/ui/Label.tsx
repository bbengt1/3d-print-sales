import * as LabelPrimitive from '@radix-ui/react-label';
import { forwardRef, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

type LabelRef = React.ElementRef<typeof LabelPrimitive.Root>;
type LabelBaseProps = React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>;

export interface LabelProps extends LabelBaseProps {
  /**
   * When true, renders a trailing `*` in destructive color to signal the
   * associated field is required. Does not set any form-validation
   * behavior — pair with `required` on the associated input to enforce.
   */
  required?: boolean;
}

export const Label = forwardRef<LabelRef, LabelProps>(function Label(
  { className, required = false, children, ...props },
  ref,
) {
  return (
    <LabelPrimitive.Root
      ref={ref}
      className={cn(
        'text-sm font-medium leading-none text-foreground peer-disabled:cursor-not-allowed peer-disabled:opacity-50',
        className,
      )}
      {...props}
    >
      {children}
      {required ? (
        <span aria-hidden="true" className="ml-0.5 text-destructive">
          *
        </span>
      ) : null}
    </LabelPrimitive.Root>
  );
});

/** Shared export in case callers need to compose a label manually. */
export function RequiredMarker({ className }: { className?: string }): ReactNode {
  return (
    <span aria-hidden="true" className={cn('ml-0.5 text-destructive', className)}>
      *
    </span>
  );
}
