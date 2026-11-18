import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { submitEvent, type SubmitEventPayload } from '../api/events';
import { TagInput } from '../components/TagInput';

interface FormState {
  source: string;
  title: string;
  event_date: string;
  raw_content: string;
  location: string;
  source_url: string;
  affected_regions: string[];
  tags: string[];
}

const EMPTY_FORM: FormState = {
  source: '',
  title: '',
  event_date: '',
  raw_content: '',
  location: '',
  source_url: '',
  affected_regions: [],
  tags: [],
};

interface SuccessInfo {
  event_id: string;
  correlation_id: string;
}

export default function SubmitEvent() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState<SuccessInfo | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  function updateField<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setValidationError(null);
  }

  function validate(): string | null {
    if (!form.source.trim()) return 'Source is required.';
    if (!form.title.trim()) return 'Title is required.';
    if (!form.event_date) return 'Event date is required.';
    if (!form.raw_content.trim()) return 'Raw content is required.';
    if (form.affected_regions.length === 0) return 'At least one affected region is required.';
    return null;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSuccess(null);

    const err = validate();
    if (err) { setValidationError(err); return; }

    setIsSubmitting(true);
    try {
      const payload: SubmitEventPayload = {
        source: form.source.trim(),
        title: form.title.trim(),
        event_date: new Date(form.event_date).toISOString(),
        raw_content: form.raw_content.trim(),
        affected_regions: form.affected_regions,
        ...(form.location.trim() ? { location: form.location.trim() } : {}),
        ...(form.source_url.trim() ? { source_url: form.source_url.trim() } : {}),
        ...(form.tags.length > 0 ? { tags: form.tags } : {}),
      };

      const result = await submitEvent(payload);
      setSuccess({ event_id: result.event_id, correlation_id: result.correlation_id });
      setForm(EMPTY_FORM);
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  const labelClass = 'block text-sm font-medium text-slate-300 mb-1.5';
  const inputClass =
    'w-full bg-slate-800/50 border border-slate-600 rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-cyan-500 transition-colors';

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Submit Event</h1>
        <p className="text-slate-400 text-sm mt-1">Submit a new intelligence event for processing.</p>
      </div>

      {/* Success banner */}
      {success && (
        <div className="bg-green-900/50 border border-green-700 rounded-xl p-4 space-y-1">
          <div className="flex items-center gap-2 text-green-300 font-semibold">
            <CheckCircle size={18} /> Event submitted successfully
          </div>
          <p className="text-green-400 text-sm">
            Event ID: <span className="font-mono">{success.event_id}</span>
          </p>
          <p className="text-green-400 text-sm">
            Correlation ID: <span className="font-mono">{success.correlation_id}</span>
          </p>
          <Link
            to={`/events/${success.event_id}`}
            className="inline-block mt-2 text-sm text-cyan-400 hover:text-cyan-300 underline transition-colors"
          >
            View Event →
          </Link>
        </div>
      )}

      {/* Error banners */}
      {validationError && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 flex items-center gap-2 text-red-300 text-sm">
          <AlertCircle size={16} className="shrink-0" /> {validationError}
        </div>
      )}
      {submitError && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-3 flex items-center gap-2 text-red-300 text-sm">
          <AlertCircle size={16} className="shrink-0" /> {submitError}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Source */}
        <div>
          <label className={labelClass}>
            Source <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={form.source}
            onChange={(e) => updateField('source', e.target.value)}
            placeholder="e.g. Reuters, BBC, Internal Report"
            className={inputClass}
            required
          />
        </div>

        {/* Title */}
        <div>
          <label className={labelClass}>
            Title <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => updateField('title', e.target.value)}
            placeholder="Event title or headline"
            className={inputClass}
            required
          />
        </div>

        {/* Event Date */}
        <div>
          <label className={labelClass}>
            Event Date <span className="text-red-400">*</span>
          </label>
          <input
            type="datetime-local"
            value={form.event_date}
            onChange={(e) => updateField('event_date', e.target.value)}
            className={inputClass}
            required
          />
        </div>

        {/* Raw Content */}
        <div>
          <label className={labelClass}>
            Raw Content <span className="text-red-400">*</span>
          </label>
          <textarea
            rows={6}
            value={form.raw_content}
            onChange={(e) => updateField('raw_content', e.target.value)}
            placeholder="Full text of the event or intelligence report…"
            className={inputClass + ' resize-y'}
            required
          />
        </div>

        {/* Location */}
        <div>
          <label className={labelClass}>Location</label>
          <input
            type="text"
            value={form.location}
            onChange={(e) => updateField('location', e.target.value)}
            placeholder="e.g. Kyiv, Ukraine"
            className={inputClass}
          />
        </div>

        {/* Source URL */}
        <div>
          <label className={labelClass}>Source URL</label>
          <input
            type="url"
            value={form.source_url}
            onChange={(e) => updateField('source_url', e.target.value)}
            placeholder="https://…"
            className={inputClass}
          />
        </div>

        {/* Affected Regions */}
        <div>
          <label className={labelClass}>
            Affected Regions <span className="text-red-400">*</span>
          </label>
          <TagInput
            tags={form.affected_regions}
            onChange={(tags) => updateField('affected_regions', tags)}
            placeholder="Type a region and press Enter…"
          />
          <p className="text-xs text-slate-500 mt-1">Press Enter or comma to add each region.</p>
        </div>

        {/* Tags */}
        <div>
          <label className={labelClass}>Tags</label>
          <TagInput
            tags={form.tags}
            onChange={(tags) => updateField('tags', tags)}
            placeholder="Type a tag and press Enter…"
          />
          <p className="text-xs text-slate-500 mt-1">Optional. Press Enter or comma to add each tag.</p>
        </div>

        {/* Submit */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex items-center gap-2 px-6 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-800 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-lg transition-colors"
          >
            {isSubmitting && <Loader2 size={16} className="animate-spin" />}
            {isSubmitting ? 'Submitting…' : 'Submit Event'}
          </button>
        </div>
      </form>
    </div>
  );
}
