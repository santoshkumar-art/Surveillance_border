/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#050505',
          900: '#0a0a0b',
          850: '#0f0f11',
          800: '#141417',
          700: '#1c1c20',
          600: '#26262b',
          500: '#3a3a41',
        },
        severity: {
          critical: '#ff4d4f',
          high: '#ff9f43',
          medium: '#ffd166',
          low: '#7bdcb5',
        },
      },
      fontFamily: {
        sans: ['Inter', 'SamsungOne', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: {
        xl: '14px',
        '2xl': '20px',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0', transform: 'translateY(4px)' }, to: { opacity: '1', transform: 'none' } },
        'slide-in': { from: { opacity: '0', transform: 'translateX(16px)' }, to: { opacity: '1', transform: 'none' } },
        'pulse-ring': { '0%': { boxShadow: '0 0 0 0 rgba(255,77,79,0.5)' }, '100%': { boxShadow: '0 0 0 12px rgba(255,77,79,0)' } },
      },
      animation: {
        'fade-in': 'fade-in 0.25s ease-out both',
        'slide-in': 'slide-in 0.28s ease-out both',
        'pulse-ring': 'pulse-ring 1.6s ease-out infinite',
      },
    },
  },
  plugins: [],
}
