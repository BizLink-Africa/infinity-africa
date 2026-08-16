import { DocsShell } from "@/components/docs/docs-shell";

export const metadata = {
  title: {
    template: "%s | Infinity Africa Developer Docs",
    default: "Infinity Africa Developer Docs",
  },
  description: "REST API reference and integration guides for the Infinity Africa payments platform.",
};

export default function DevelopersLayout({ children }: { children: React.ReactNode }) {
  return <DocsShell>{children}</DocsShell>;
}
