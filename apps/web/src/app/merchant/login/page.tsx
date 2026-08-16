import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { LoginForm } from "@/components/auth/login-form";

export const metadata = {
  title: "Merchant Login | Infinity Africa",
};

export default function MerchantLoginPage() {
  return (
    <AuthSplitLayout>
      <h1 className="text-2xl font-bold text-on-surface">Merchant Portal Login</h1>
      <p className="mt-2 text-sm text-on-surface-variant">Sign in to manage your Infinity Africa merchant account.</p>
      <LoginForm variant="merchant" />
    </AuthSplitLayout>
  );
}
