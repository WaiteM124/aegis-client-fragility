import { useState, useEffect } from 'react';
import { useHealth } from '../hooks/useHealth';

function LiveClock() {
  const [time, setTime] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const formatted =
    time.getUTCHours().toString().padStart(2, '0') +
    ':' +
    time.getUTCMinutes().toString().padStart(2, '0') +
    ':' +
    time.getUTCSeconds().toString().padStart(2, '0') +
    ' UTC';

  return <span className="font-mono text-sm text-slate-400">{formatted}</span>;
}

export function TopBar() {
  const { data: health, isLoading } = useHealth();

  const isHealthy = !isLoading && health?.status === 'ok' && health.model_provider.healthy;
  const statusLabel = isLoading
    ? 'Checking…'
    : isHealthy
    ? 'Operational'
    : 'Degraded';

  return (
    <header className="fixed top-0 left-[220px] right-0 h-14 bg-slate-900/80 backdrop-blur border-b border-slate-700/50 z-10 flex items-center justify-end px-6 gap-4">
      {/* System status */}
      <div className="flex items-center gap-2">
        <span
          className={`w-2 h-2 rounded-full ${
            isLoading
              ? 'bg-slate-500'
              : isHealthy
              ? 'bg-green-400 animate-pulse'
              : 'bg-red-500'
          }`}
        />
        <span className="text-sm text-slate-400">{statusLabel}</span>
      </div>

      <div className="w-px h-5 bg-slate-700" />

      <LiveClock />
    </header>
  );
}
