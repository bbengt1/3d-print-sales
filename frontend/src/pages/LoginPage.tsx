import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Printer } from 'lucide-react';
import { z } from 'zod';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';
import { useAuthStore } from '@/store/auth';
import { getApiErrorMessage } from '@/lib/apiError';
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

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/control-center';

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
    } catch (err) {
      setErrors({ form: getApiErrorMessage(err, 'Invalid email or password') });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="absolute top-4 right-4">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={toggle}
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>Toggle theme</TooltipContent>
        </Tooltip>
      </div>

      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 text-primary mb-8">
          <Printer className="w-10 h-10" />
          <span className="text-2xl font-semibold">3D Print Sales</span>
        </div>
        <div className="bg-card border border-border rounded-lg p-8 shadow-sm">
          <h2 className="text-base font-semibold mb-6 text-center">Sign In</h2>
          {errors.form && (
            <div className="bg-destructive/10 text-destructive text-sm rounded-lg p-3 mb-4">
              {errors.form}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="login-email">Email</Label>
              <Input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
                invalid={Boolean(errors.email)}
              />
              {errors.email && (
                <p className="text-destructive text-xs">{errors.email}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                invalid={Boolean(errors.password)}
              />
              {errors.password && (
                <p className="text-destructive text-xs">{errors.password}</p>
              )}
            </div>
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>
        </div>
        <p className="text-center text-xs text-muted-foreground mt-4">
          Sign in with the admin credentials configured for this environment.
        </p>
      </div>
    </div>
  );
}
