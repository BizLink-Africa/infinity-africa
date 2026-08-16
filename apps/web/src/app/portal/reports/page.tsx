"use client";

import { useState } from "react";

import { Card } from "@/components/portal/card";
import { EmptyState } from "@/components/portal/empty-state";
import { Icon } from "@/components/portal/icon";
import { PageHeader } from "@/components/portal/page-header";
import { SegmentedControl } from "@/components/portal/segmented-control";

const REPORT_TYPES = ["Transactions Summary", "Withdrawals Summary", "Fees Summary", "Customer Statement"];

export default function ReportsPage() {
  const [format, setFormat] = useState<"PDF" | "CSV">("PDF");
  const [generating, setGenerating] = useState(false);
  const [generatedCount, setGeneratedCount] = useState(0);

  function handleGenerate(event: React.FormEvent) {
    event.preventDefault();
    setGenerating(true);
    // Mirrors a real "POST /v1/merchants/{id}/reports" call — apps/api
    // doesn't have a reports endpoint yet, so this just simulates the
    // async generation state for the prototype.
    setTimeout(() => {
      setGenerating(false);
      setGeneratedCount((count) => count + 1);
    }, 600);
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Reports" description="Generate reports for accounting, reconciliation, and tax filing." />

      <Card>
        <h3 className="text-2xl font-semibold text-on-background mb-5">Generate a Report</h3>
        <form onSubmit={handleGenerate} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1.5">Report Type</label>
            <select className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm">
              {REPORT_TYPES.map((type) => (
                <option key={type}>{type}</option>
              ))}
            </select>
          </div>
          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">From</label>
              <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" type="date" />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1.5">To</label>
              <input className="w-full px-3.5 py-2.5 bg-surface-container-low border border-surface-container-highest rounded-lg text-sm" type="date" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-2">Format</label>
            <SegmentedControl
              options={[
                { value: "PDF" as const, label: "PDF" },
                { value: "CSV" as const, label: "CSV" },
              ]}
              value={format}
              onChange={setFormat}
            />
          </div>
          <button
            type="submit"
            disabled={generating}
            className="bg-primary-container text-on-primary text-sm font-medium py-3 px-6 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-60"
          >
            <Icon name="bar_chart" className="text-[20px]" />
            {generating ? "Generating…" : "Generate Report"}
          </button>
        </form>
      </Card>

      <Card>
        {generatedCount === 0 ? (
          <EmptyState
            icon="description"
            heading="No reports generated yet"
            body="Reports you generate will appear here, ready to download as PDF or CSV."
            actionLabel="Generate Your First Report"
            onAction={() => document.querySelector("form")?.requestSubmit()}
          />
        ) : (
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-3">
              <Icon name="task_alt" className="text-primary" />
              <span className="text-sm text-on-background">
                {generatedCount} report{generatedCount > 1 ? "s" : ""} generated this session.
              </span>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
