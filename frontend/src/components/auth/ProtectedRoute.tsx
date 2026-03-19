import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import api from '@/api/client';

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, user, setUser, logout } = useAuthStore();
  const location = useLocation();
  const [checking, setChecking] = useState(!user && !!token);

  useEffect(() => {
    if (token && !user) {
      api
        .get('/auth/me')
        .then(({ data }) => setUser(data))
        .catch(() => logout())
        .finally(() => setChecking(false));
    }
  }, [token, user, setUser, logout]);

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-muted-foreground">
          <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span>Loading...</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
