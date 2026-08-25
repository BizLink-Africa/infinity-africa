import { redirect } from "next/navigation";

export default function PortalApiLogsRedirect() {
  redirect("/portal/api-credentials?tab=logs");
}
