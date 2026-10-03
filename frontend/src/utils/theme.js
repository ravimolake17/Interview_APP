export const PRIMARY_COLORS = [
  { id: 'orange', label: 'Orange', primary: '#f97316', light: '#fb923c', dark: '#ea580c' },
  { id: 'blue', label: 'Blue', primary: '#2563eb', light: '#3b82f6', dark: '#1d4ed8' },
  { id: 'purple', label: 'Purple', primary: '#7c3aed', light: '#8b5cf6', dark: '#6d28d9' },
  { id: 'green', label: 'Green', primary: '#059669', light: '#10b981', dark: '#047857' },
  { id: 'red', label: 'Red', primary: '#dc2626', light: '#ef4444', dark: '#b91c1c' },
];

export const DEFAULT_APPEARANCE = {
  theme: 'light',
  primaryColorId: 'orange',
};

const STORAGE_PREFIX = 'rr-parkon-appearance';

function storageKey(userId) {
  return userId ? `${STORAGE_PREFIX}-${userId}` : `${STORAGE_PREFIX}-guest`;
}

export function getPrimaryColor(primaryColorId) {
  return PRIMARY_COLORS.find((color) => color.id === primaryColorId) || PRIMARY_COLORS[0];
}

export function loadAppearanceSettings(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return { ...DEFAULT_APPEARANCE };
    const parsed = JSON.parse(raw);
    const validColor = PRIMARY_COLORS.some((color) => color.id === parsed.primaryColorId);
    return {
      theme: parsed.theme === 'dark' ? 'dark' : 'light',
      primaryColorId: validColor ? parsed.primaryColorId : DEFAULT_APPEARANCE.primaryColorId,
    };
  } catch {
    return { ...DEFAULT_APPEARANCE };
  }
}

export function saveAppearanceSettings(userId, appearance) {
  localStorage.setItem(storageKey(userId), JSON.stringify(appearance));
}

export function applyAppearance(appearance) {
  const palette = getPrimaryColor(appearance.primaryColorId);
  const root = document.documentElement;

  root.style.setProperty('--color-primary', palette.primary);
  root.style.setProperty('--color-primary-light', palette.light);
  root.style.setProperty('--color-primary-dark', palette.dark);
  root.style.setProperty('--color-sidebar-active', palette.primary);

  if (appearance.theme === 'dark') root.classList.add('dark');
  else root.classList.remove('dark');
}
