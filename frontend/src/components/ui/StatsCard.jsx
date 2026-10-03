import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown } from 'lucide-react';

export default function StatsCard({ title, value, icon: Icon, color, trend, trendValue, delay = 0 }) {
  const colorMap = {
    blue: { bg: 'bg-blue-50 dark:bg-blue-900/20', text: 'text-blue-600', ring: 'ring-blue-100 dark:ring-blue-800' },
    green: { bg: 'bg-green-50 dark:bg-green-900/20', text: 'text-green-600', ring: 'ring-green-100 dark:ring-green-800' },
    amber: { bg: 'bg-amber-50 dark:bg-amber-900/20', text: 'text-amber-600', ring: 'ring-amber-100 dark:ring-amber-800' },
    violet: { bg: 'bg-violet-50 dark:bg-violet-900/20', text: 'text-violet-600', ring: 'ring-violet-100 dark:ring-violet-800' },
    red: { bg: 'bg-red-50 dark:bg-red-900/20', text: 'text-red-500', ring: 'ring-red-100 dark:ring-red-800' },
    cyan: { bg: 'bg-cyan-50 dark:bg-cyan-900/20', text: 'text-cyan-600', ring: 'ring-cyan-100 dark:ring-cyan-800' },
    teal: { bg: 'bg-teal-50 dark:bg-teal-900/20', text: 'text-teal-600', ring: 'ring-teal-100 dark:ring-teal-800' },
  };
  const c = colorMap[color] || colorMap.blue;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className="card card-hover p-5 flex items-start justify-between"
    >
      <div>
        <p className="text-xs font-medium text-muted uppercase tracking-wider mb-1">{title}</p>
        <p className="text-3xl font-bold text-col mt-1">{value}</p>
        {trendValue !== undefined && (
          <div className={`flex items-center gap-1 mt-2 text-xs font-medium ${trend === 'up' ? 'text-green-500' : 'text-red-500'}`}>
            {trend === 'up' ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            <span>{trendValue}% vs last month</span>
          </div>
        )}
      </div>
      <div className={`w-11 h-11 rounded-2xl ${c.bg} ring-1 ${c.ring} flex items-center justify-center`}>
        <Icon size={20} className={c.text} />
      </div>
    </motion.div>
  );
}
