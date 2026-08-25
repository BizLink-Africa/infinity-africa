import { redirect } from "next/navigation";

export default function PortalDeveloperDocsRedirect() {
  redirect("/portal/api-credentials?tab=docs");
}
