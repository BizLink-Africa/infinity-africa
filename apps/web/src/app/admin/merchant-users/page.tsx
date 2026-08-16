import { redirect } from "next/navigation";

export default function AdminMerchantUsersRedirect() {
  redirect("/super-admin/merchant-users");
}
