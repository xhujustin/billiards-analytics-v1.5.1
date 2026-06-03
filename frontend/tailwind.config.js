/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cue: {
          bg: '#F8FAFC',
          ink: '#111827',
          muted: '#6B7280',
          line: '#E5E7EB',
          primary: '#4F46E5',
          success: '#22C55E',
          danger: '#EF4444',
          warning: '#F59E0B',
        },
      },
      boxShadow: {
        soft: '0 14px 38px rgba(15, 23, 42, 0.08)',
        card: '0 8px 26px rgba(15, 23, 42, 0.06)',
      },
    },
  },
  plugins: [],
};
