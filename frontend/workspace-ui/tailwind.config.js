/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        workspace: {
          bg: '#0b1020',
          panel: '#111a2e',
          muted: '#1a2540',
          border: '#223257',
          text: '#e6edf8',
          accent: '#6ea8fe',
        },
      },
    },
  },
  plugins: [],
}
