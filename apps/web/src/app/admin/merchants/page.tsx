import { redirect } from "next/navigation";

export default function AdminMerchantsRedirect() {
  redirect("/super-admin/merchants");
}
