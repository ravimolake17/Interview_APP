import { useEffect, useState } from 'react';
import Modal from './Modal';

export default function DuplicateJobDialog({
  open,
  existing,
  reason,
  suggestedTitle,
  onReplace,
  onRename,
  onCancel,
}) {
  const [renameTitle, setRenameTitle] = useState(suggestedTitle || '');

  useEffect(() => {
    if (open) setRenameTitle(suggestedTitle || '');
  }, [open, suggestedTitle]);

  const existingTitle = existing?.title || 'this job';
  const isFile = reason === 'file';

  return (
    <Modal open={open} onClose={onCancel} title="Duplicate job description" size="sm">
      <div className="space-y-4">
        <p className="text-sm text-col">
          {isFile
            ? `This JD file is already stored as “${existingTitle}”.`
            : `A job titled “${existingTitle}” already exists.`}
          {' '}Replace the existing Jobs entry, or save this JD under a new title.
        </p>
        <div>
          <label htmlFor="duplicate-rename-title" className="text-xs font-medium text-muted mb-1.5 block">
            New title (if renaming)
          </label>
          <input
            id="duplicate-rename-title"
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-xl border border-col bg-transparent text-col focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          />
        </div>
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-2 rounded-xl border border-col text-sm font-medium text-muted hover:text-col"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onRename((renameTitle || '').trim())}
            className="px-3 py-2 rounded-xl border border-col text-sm font-medium text-col hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            Rename and save
          </button>
          <button
            type="button"
            onClick={onReplace}
            className="px-3 py-2 rounded-xl bg-primary-accent text-white text-sm font-semibold hover:opacity-90"
          >
            Replace existing
          </button>
        </div>
      </div>
    </Modal>
  );
}
