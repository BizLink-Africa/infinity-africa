import { redirect } from "next/navigation";

export default function AdminTransactionsRedirect() {
  redirect("/super-admin/transactions");
}
