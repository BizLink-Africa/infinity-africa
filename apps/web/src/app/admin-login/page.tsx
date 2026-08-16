import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { LoginForm } from "@/components/auth/login-form";

export const metadata = {
  title: "Super Admin Login | Infinity Africa",
};

export default function AdminLoginPage() {
  return (
    <AuthSplitLayout>
      <h1 className="text-2xl font-bold text-on-surface">Super Admin Login</h1>
      <p className="mt-2 text-sm text-on-surface-variant">Sign in to the Infinity Africa platform admin console.</p>
      <LoginForm variant="admin" />
    </AuthSplitLayout>
  );
}
