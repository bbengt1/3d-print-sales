import { useState } from 'react';
import { ImageOff } from 'lucide-react';
import { cn } from '@/lib/utils';

type PrinterThumbnailProps = {
  src?: string | null;
  alt: string;
  className?: string;
  imgClassName?: string;
  fallbackLabel?: string;
};

export default function PrinterThumbnail({ src, alt, className, imgClassName, fallbackLabel = 'No thumbnail' }: PrinterThumbnailProps) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(src) && !failed;

  return (
    <div className={cn('overflow-hidden rounded-lg border border-border bg-background/40', className)}>
      {showImage ? (
        <img
          src={src || undefined}
          alt={alt}
          loading="lazy"
          onError={() => setFailed(true)}
          className={cn('h-full w-full object-cover', imgClassName)}
        />
      ) : (
        <div className="flex h-full min-h-[120px] w-full flex-col items-center justify-center gap-2 px-4 py-6 text-center text-muted-foreground">
          <ImageOff className="h-6 w-6" />
          <p className="text-xs">{fallbackLabel}</p>
        </div>
      )}
    </div>
  );
}
