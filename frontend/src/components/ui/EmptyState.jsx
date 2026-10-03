import { motion } from 'framer-motion';

export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 px-6 text-center"
    >
      <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4">
        {Icon && <Icon size={28} className="text-muted" />}
      </div>
      <h3 className="text-base font-semibold text-col mb-1">{title}</h3>
      <p className="text-sm text-muted max-w-xs mb-5">{description}</p>
      {action}
    </motion.div>
  );
}
