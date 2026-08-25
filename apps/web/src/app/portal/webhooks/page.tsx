import { redirect } from "next/navigation";

export default function PortalWebhooksRedirect() {
  redirect("/portal/api-credentials?tab=webhooks");
}
