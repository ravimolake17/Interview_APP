import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, File, X, CheckCircle2 } from 'lucide-react';

function toFileList(incoming) {
  if (!incoming) return [];
  return Array.from(incoming).filter((file) => file && typeof file.name === 'string');
}

export default function FileUploader({ onFiles, accept = '*', multiple = false, label = 'Drop files here', hint = '' }) {
  const [files, setFiles] = useState([]);
  const filesRef = useRef([]);
  const inputRef = useRef(null);

  const notifyParent = useCallback((next) => {
    filesRef.current = next;
    if (!onFiles) return;
    onFiles(multiple ? next : next[0] || null);
  }, [multiple, onFiles]);

  const processFiles = useCallback((incoming) => {
    const arr = toFileList(incoming);
    if (!arr.length) return;

    const next = multiple ? [...filesRef.current, ...arr] : arr;
    setFiles(next);
    notifyParent(next);

    if (inputRef.current) inputRef.current.value = '';
  }, [multiple, notifyParent]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    processFiles(e.dataTransfer.files);
  }, [processFiles]);

  const removeFile = useCallback((idx) => {
    const next = filesRef.current.filter((_, i) => i !== idx);
    setFiles(next);
    notifyParent(next);
  }, [notifyParent]);

  const [dragging, setDragging] = useState(false);

  const fmt = (bytes) => bytes > 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${(bytes / 1024).toFixed(0)} KB`;

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200
          ${dragging
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 scale-[1.01]'
            : 'border-col hover:border-blue-400 hover:bg-slate-50 dark:hover:bg-slate-800/50'
          }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={(e) => {
            processFiles(e.target.files);
            e.target.value = '';
          }}
        />
        <motion.div animate={{ y: dragging ? -4 : 0 }} transition={{ duration: 0.2 }}>
          <div className="w-12 h-12 rounded-2xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mx-auto mb-3">
            <Upload size={22} className="text-blue-500" />
          </div>
          <p className="text-sm font-medium text-col mb-1">{label}</p>
          <p className="text-xs text-muted">{hint || `${accept.replace(/,/g, ', ')} • Click or drag`}</p>
        </motion.div>
      </div>

      <AnimatePresence>
        {files.map((file, i) => (
          <motion.div
            key={`${file.name}-${file.size}-${i}`}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.15 }}
            className="flex items-center gap-3 card px-4 py-3"
          >
            <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center flex-shrink-0">
              <File size={16} className="text-blue-500" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-col truncate">{file.name}</p>
              <p className="text-xs text-muted">{fmt(file.size)}</p>
            </div>
            <CheckCircle2 size={16} className="text-green-500 flex-shrink-0" />
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); removeFile(i); }}
              className="text-muted hover:text-red-500 transition-colors flex-shrink-0"
            >
              <X size={16} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
