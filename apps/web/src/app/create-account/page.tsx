import { AuthSplitLayout } from "@/components/auth/auth-split-layout";
import { CreateAccountForm } from "@/components/auth/create-account-form";

export const metadata = {
  title: "Create Account | Infinity Africa",
  description: "Create your Infinity Africa merchant account.",
};

export default function CreateAccountPage() {
  return (
    <AuthSplitLayout maxWidthClassName="max-w-md">
      <h1 className="text-2xl font-bold text-on-surface">Create your merchant account</h1>
      <p className="mt-2 text-sm text-on-surface-variant">
        Start collecting payments with Infinity Africa. After creating your account, you&apos;ll complete a short onboarding
        form with your business details.
      </p>
      <CreateAccountForm />
    </AuthSplitLayout>
  );
}
