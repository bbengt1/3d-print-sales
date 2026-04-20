export default function Footer() {
  return (
    <footer className="mt-auto border-t border-border bg-card/30 py-6 backdrop-blur">
      <div className="mx-auto flex max-w-[96rem] flex-col gap-2 px-4 text-center text-sm text-muted-foreground sm:px-6 lg:px-8 lg:flex-row lg:items-center lg:justify-between">
        <p>&copy; {new Date().getFullYear()} 3D Print Sales.</p>
        <p className="text-xs text-muted-foreground/90">
          Control Center • Print Floor • Sell • Stock • Product Studio
        </p>
      </div>
    </footer>
  );
}
