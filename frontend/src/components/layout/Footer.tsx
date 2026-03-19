export default function Footer() {
  return (
    <footer className="border-t border-border py-6 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-muted-foreground">
        &copy; {new Date().getFullYear()} 3D Print Sales. All rights reserved.
      </div>
    </footer>
  );
}
