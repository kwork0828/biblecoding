/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#FAF7F1',
        surface: '#FFFFFF',
        ink: '#2A2823',
        'ink-soft': '#6B6455',
        border: '#E7E1D4',
        accent: '#3E7A5E',
        'accent-dark': '#2F5F47',
        'accent-soft': '#E4EFE8',
        warn: '#B5754A',
        danger: '#C1553F',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Apple SD Gothic Neo"', '"Noto Sans KR"', 'sans-serif'],
        serif: ['Georgia', '"Noto Serif KR"', 'serif'],
      },
    },
  },
  plugins: [],
};
