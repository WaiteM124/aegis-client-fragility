import { useState, type KeyboardEvent } from 'react';
import { X } from 'lucide-react';

interface TagInputProps {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}

export function TagInput({ tags, onChange, placeholder }: TagInputProps) {
  const [input, setInput] = useState('');

  function addTag(value: string) {
    const trimmed = value.trim().replace(/,$/, '').trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setInput('');
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(input);
    } else if (e.key === 'Backspace' && input === '' && tags.length > 0) {
      onChange(tags.slice(0, -1));
    }
  }

  function removeTag(tag: string) {
    onChange(tags.filter((t) => t !== tag));
  }

  return (
    <div className="bg-slate-700/50 border border-slate-600 rounded-lg p-2 flex flex-wrap gap-1 min-h-[44px]">
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 bg-cyan-900/50 text-cyan-300 text-xs px-2 py-1 rounded-full"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(tag)}
            className="hover:text-white transition-colors"
            aria-label={`Remove ${tag}`}
          >
            <X size={12} />
          </button>
        </span>
      ))}
      <input
        type="text"
        value={input}
        onChange={(e) => {
          const val = e.target.value;
          if (val.includes(',')) {
            addTag(val);
          } else {
            setInput(val);
          }
        }}
        onKeyDown={handleKeyDown}
        placeholder={tags.length === 0 ? (placeholder ?? 'Type and press Enter...') : ''}
        className="flex-1 min-w-[120px] bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none py-0.5"
      />
    </div>
  );
}
