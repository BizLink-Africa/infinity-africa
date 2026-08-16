import { redirect } from "next/navigation";

export default function AdminCollectionsRedirect() {
  redirect("/super-admin/collections");
}
