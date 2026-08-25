import { redirect } from "next/navigation";

export default function PortalApiKeysRedirect() {
  redirect("/portal/api-credentials?tab=keys");
}
