import { redirect } from "next/navigation";

export default function AdminWebhooksRedirect() {
  redirect("/super-admin/webhooks");
}
