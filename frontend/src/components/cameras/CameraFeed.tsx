import { useEffect, useRef, useState, useCallback } from 'react';
import { VideoOff, RefreshCw } from 'lucide-react';

type FeedStatus = 'connecting' | 'live' | 'error' | 'offline';

interface CameraFeedProps {
  mseWsUrl: string | null;
  snapshotUrl: string | null;
  alt?: string;
  className?: string;
  showLiveBadge?: boolean;
  onStatusChange?: (status: FeedStatus) => void;
}

const MAX_RETRIES = 4;
const RETRY_BASE_MS = 3000;
const MJPEG_POLL_MS = 2000;
const BUFFER_CLEANUP_INTERVAL_MS = 10000;
const BUFFER_MAX_SECONDS = 30;

export default function CameraFeed({
  mseWsUrl,
  snapshotUrl,
  alt = 'Camera feed',
  className = '',
  showLiveBadge = true,
  onStatusChange,
}: CameraFeedProps) {
  const [status, setStatus] = useState<FeedStatus>('connecting');
  const [useMjpeg, setUseMjpeg] = useState(false);
  const [mjpegSrc, setMjpegSrc] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mjpegTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cleanupTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const updateStatus = useCallback(
    (s: FeedStatus) => {
      setStatus(s);
      onStatusChange?.(s);
    },
    [onStatusChange],
  );

  // ── Cleanup all resources ──
  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (mjpegTimerRef.current) {
      clearInterval(mjpegTimerRef.current);
      mjpegTimerRef.current = null;
    }
    if (cleanupTimerRef.current) {
      clearInterval(cleanupTimerRef.current);
      cleanupTimerRef.current = null;
    }
    if (mediaSourceRef.current && videoRef.current) {
      try {
        if (videoRef.current.src) {
          URL.revokeObjectURL(videoRef.current.src);
        }
      } catch {
        // ignore
      }
    }
    mediaSourceRef.current = null;
    sourceBufferRef.current = null;
  }, []);

  // ── MJPEG fallback polling ──
  const startMjpeg = useCallback(() => {
    if (!snapshotUrl) {
      updateStatus('offline');
      return;
    }
    setUseMjpeg(true);
    const refresh = () => {
      if (!mountedRef.current) return;
      setMjpegSrc(`${snapshotUrl}?t=${Date.now()}`);
      updateStatus('live');
    };
    refresh();
    mjpegTimerRef.current = setInterval(refresh, MJPEG_POLL_MS);
  }, [snapshotUrl, updateStatus]);

  // ── MSE WebSocket connection ──
  const connectMse = useCallback(() => {
    if (!mseWsUrl || !mountedRef.current) {
      startMjpeg();
      return;
    }
    if (!('MediaSource' in window)) {
      startMjpeg();
      return;
    }

    updateStatus('connecting');

    const ms = new MediaSource();
    mediaSourceRef.current = ms;
    const video = videoRef.current;
    if (!video) return;

    video.src = URL.createObjectURL(ms);

    let codec = '';
    let initDone = false;

    ms.addEventListener('sourceopen', () => {
      // sourceopen fires after we set video.src
    });

    const ws = new WebSocket(mseWsUrl);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    const connectionTimeout = setTimeout(() => {
      if (!initDone && mountedRef.current) {
        ws.close();
      }
    }, 8000);

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;

      if (typeof event.data === 'string') {
        // First message is JSON with codec info
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'mse' && msg.value) {
            codec = msg.value;
          }
        } catch {
          // ignore parse errors
        }
        return;
      }

      // Binary frame data
      if (!initDone && ms.readyState === 'open') {
        clearTimeout(connectionTimeout);
        try {
          const sb = ms.addSourceBuffer(codec || 'video/avc; codecs="avc1.640029"');
          sourceBufferRef.current = sb;
          initDone = true;
          retryCountRef.current = 0;
          updateStatus('live');

          // Periodic buffer cleanup to prevent memory growth
          cleanupTimerRef.current = setInterval(() => {
            if (sb.updating || ms.readyState !== 'open') return;
            try {
              const buffered = sb.buffered;
              if (buffered.length > 0) {
                const end = buffered.end(buffered.length - 1);
                const start = buffered.start(0);
                if (end - start > BUFFER_MAX_SECONDS) {
                  sb.remove(start, end - BUFFER_MAX_SECONDS);
                }
              }
            } catch {
              // ignore
            }
          }, BUFFER_CLEANUP_INTERVAL_MS);
        } catch {
          // Codec not supported, fall back to MJPEG
          cleanup();
          startMjpeg();
          return;
        }
      }

      const sb = sourceBufferRef.current;
      if (sb && !sb.updating && ms.readyState === 'open') {
        try {
          sb.appendBuffer(event.data);
        } catch {
          // Buffer full or closed — ignore
        }
      }
    };

    ws.onerror = () => {
      clearTimeout(connectionTimeout);
    };

    ws.onclose = () => {
      clearTimeout(connectionTimeout);
      if (!mountedRef.current) return;

      if (retryCountRef.current < MAX_RETRIES) {
        const delay = RETRY_BASE_MS * Math.pow(2, retryCountRef.current);
        retryCountRef.current++;
        updateStatus('connecting');
        cleanup();
        retryTimerRef.current = setTimeout(() => {
          if (mountedRef.current) connectMse();
        }, delay);
      } else {
        cleanup();
        startMjpeg();
      }
    };
  }, [mseWsUrl, cleanup, startMjpeg, updateStatus]);

  // ── Visibility API: pause when hidden, reconnect when visible ──
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) {
        cleanup();
      } else if (mountedRef.current) {
        retryCountRef.current = 0;
        setUseMjpeg(false);
        connectMse();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [cleanup, connectMse]);

  // ── Main effect: connect on mount ──
  useEffect(() => {
    mountedRef.current = true;
    connectMse();
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [connectMse, cleanup]);

  const handleRetry = () => {
    cleanup();
    retryCountRef.current = 0;
    setUseMjpeg(false);
    setMjpegSrc(null);
    connectMse();
  };

  // ── No URLs at all ──
  if (!mseWsUrl && !snapshotUrl) {
    return (
      <div className={`flex items-center justify-center bg-black/60 text-muted-foreground ${className}`}>
        <div className="flex flex-col items-center gap-2">
          <VideoOff className="h-8 w-8 opacity-50" />
          <span className="text-xs">No camera configured</span>
        </div>
      </div>
    );
  }

  // ── Error / Offline state ──
  if (status === 'error' || status === 'offline') {
    return (
      <div className={`flex items-center justify-center bg-black/60 text-muted-foreground ${className}`}>
        <div className="flex flex-col items-center gap-2">
          <VideoOff className="h-8 w-8 text-danger opacity-70" />
          <span className="text-xs">Camera offline</span>
          <button
            type="button"
            onClick={handleRetry}
            className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative bg-black overflow-hidden ${className}`}>
      {/* MSE video */}
      {!useMjpeg && (
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="w-full h-full object-contain"
        />
      )}

      {/* MJPEG fallback */}
      {useMjpeg && mjpegSrc && (
        <img
          src={mjpegSrc}
          alt={alt}
          className="w-full h-full object-contain"
          onError={() => updateStatus('error')}
        />
      )}

      {/* Connecting overlay */}
      {status === 'connecting' && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/80">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className="h-2 w-2 rounded-full bg-warning animate-pulse" />
            <span className="text-xs">Connecting...</span>
          </div>
        </div>
      )}

      {/* Live badge */}
      {status === 'live' && showLiveBadge && (
        <div className="absolute top-2 right-2 flex items-center gap-1 px-1.5 py-0.5 rounded bg-danger/90 text-white text-[10px] font-semibold uppercase tracking-wider">
          <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
          Live
        </div>
      )}
    </div>
  );
}
