import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Printer } from 'lucide-react';
import { z } from 'zod';
import { toast } from 'sonner';
import api from '@/api/client';
import { useAuthStore } from '@/store/auth';
import { useTheme } from '@/hooks/useTheme';
import { Moon, Sun } from 'lucide-react';

const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
});

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const { dark, toggle } = useTheme();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    const result = loginSchema.safeParse({ email, password });
    if (!result.success) {
      const fieldErrors: Record<string, string> = {};
      result.error.issues.forEach((issue) => {
        fieldErrors[issue.path[0] as string] = issue.message;
      });
      setErrors(fieldErrors);
      return;
    }

    setLoading(true);
    try {
      const { data } = await api.post('/auth/login', { email, password });
      const token = data.access_token;
      localStorage.setItem('token', token);
      const { data: user } = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setAuth(user, token);
      toast.success(`Welcome back, ${user.full_name}`);
      navigate(from, { replace: true });
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Invalid email or password';
      setErrors({ form: message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="absolute top-4 right-4">
        <button
          onClick={toggle}
          className="p-2 rounded-md hover:bg-accent transition-colors text-muted-foreground"
          aria-label="Toggle theme"
        >
          {dark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>
      </div>

      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 text-primary mb-8">
          <Printer className="w-10 h-10" />
          <span className="text-2xl font-bold">3D Print Sales</span>
        </div>
        <div className="bg-card border border-border rounded-lg p-8 shadow-sm">
          <h2 className="text-xl font-bold mb-6 text-center">Sign In</h2>
          {errors.form && (
            <div className="bg-destructive/10 text-destructive text-sm rounded-lg p-3 mb-4">
              {errors.form}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring ${
                  errors.email ? 'border-destructive' : 'border-input'
                }`}
                placeholder="admin@example.com"
              />
              {errors.email && (
                <p className="text-destructive text-xs mt-1">{errors.email}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring ${
                  errors.password ? 'border-destructive' : 'border-input'
                }`}
                placeholder="Enter your password"
              />
              {errors.password && (
                <p className="text-destructive text-xs mt-1">{errors.password}</p>
              )}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-primary-foreground py-2.5 rounded-md font-medium hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : (
                'Sign In'
              )}
            </button>
          </form>
        </div>
        <p className="text-center text-xs text-muted-foreground mt-4">
          Sign in with the admin credentials configured for this environment.
        </p>
      </div>
    </div>
  );
}
