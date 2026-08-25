import { redirect } from "next/navigation";

export default function PortalIpAllowlistRedirect() {
  redirect("/portal/api-credentials?tab=ip-allowlist");
}
