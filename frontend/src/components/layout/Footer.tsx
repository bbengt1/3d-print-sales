export default function Footer() {
  const appVersion = import.meta.env.VITE_APP_VERSION || 'dev';

  return (
    <footer className="mt-auto border-t border-border py-3">
      <div className="mx-auto flex max-w-[88rem] flex-col gap-1 px-4 text-center text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <p>&copy; {new Date().getFullYear()} 3D Print Sales</p>
        <p className="tabular-nums text-muted-foreground/80">Build {appVersion}</p>
      </div>
    </footer>
  );
}
