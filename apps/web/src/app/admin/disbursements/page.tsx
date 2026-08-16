import { redirect } from "next/navigation";

export default function AdminDisbursementsRedirect() {
  redirect("/super-admin/withdrawals");
}
