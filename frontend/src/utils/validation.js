export function isValidEmail(value) {
  const email = value.trim();
  if (!email) return 'Email is required.';
  const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!pattern.test(email)) return 'Enter a valid email address.';
  return null;
}

export function isValidPassword(value, { minLength = 6 } = {}) {
  if (!value) return 'Password is required.';
  if (value.length < minLength) return `Password must be at least ${minLength} characters.`;
  return null;
}
