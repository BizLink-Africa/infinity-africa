"use client";

const inputClass =
  "w-full border-0 border-b border-outline-variant bg-transparent pb-2 text-sm text-on-surface placeholder-outline focus:outline-none focus:border-primary-container transition-colors";
const labelClass = "block text-xs font-semibold text-on-surface-variant uppercase tracking-wide mb-2";

export function ContactForm() {
  return (
    <form onSubmit={(event) => event.preventDefault()} className="space-y-7">
      <div className="grid sm:grid-cols-2 gap-7">
        <div>
          <label className={labelClass}>Full Name</label>
          <input type="text" placeholder="e.g. Amani Mushi" className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>Business / Company Name</label>
          <input type="text" placeholder="e.g. Amani Traders Ltd" className={inputClass} />
        </div>
      </div>
      <div>
        <label className={labelClass}>Business Type / Service Offered</label>
        <input type="text" placeholder="e.g. Online Retail, Event Planning, Delivery Service" className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Physical Location</label>
        <input type="text" placeholder="e.g. Kinondoni, Dar es Salaam" className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>How Can We Help?</label>
        <textarea rows={3} placeholder="Tell us about your business and what you need" className={`${inputClass} resize-none`} />
      </div>
      <button
        type="submit"
        className="inline-flex items-center gap-2 bg-primary-container text-on-primary text-sm font-medium px-6 py-3.5 rounded-lg hover:opacity-90 transition-opacity"
      >
        Send Message
      </button>
    </form>
  );
}
