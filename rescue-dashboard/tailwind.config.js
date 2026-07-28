export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: { 900: '#0f172a', 800: '#1e293b', 700: '#334155' },
        primary: {
          50: '#e6f3ff', 100: '#b3dcff', 200: '#80c5ff', 300: '#4daeff',
          400: '#1a97ff', 500: '#0080e6', 600: '#0066b3', 700: '#004d80',
          800: '#00334d', 900: '#001a26'
        },
        coral: {
          50: '#fff5f5', 100: '#ffe0e0', 200: '#ffb3b3', 300: '#ff8080',
          400: '#ff4d4d', 500: '#ff1a1a', 600: '#cc0000', 700: '#990000',
          800: '#660000', 900: '#330000'
        },
        teal: {
          50: '#e6fffa', 100: '#b3f5ec', 200: '#80ebe0', 300: '#4de0d4',
          400: '#1ad6c8', 500: '#00ccbc', 600: '#00a396', 700: '#007a70',
          800: '#00524a', 900: '#002924'
        }
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    }
  },
  plugins: []
}
