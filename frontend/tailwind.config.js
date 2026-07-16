/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          primary: 'hsl(38, 25%, 98%)',
          card: '#ffffff',
          dark: 'hsl(220, 24%, 10%)',
        },
        brand: {
          gold: '#c09a5f',
          'gold-hover': '#ad8449',
          'gold-light': 'hsl(38, 40%, 93%)',
          navy: '#0a1120',
          graphite: 'hsl(220, 24%, 15%)',
        }
      },
      fontFamily: {
        serif: ['Lora', 'Georgia', 'serif'],
        sans: ['Outfit', 'Inter', 'sans-serif'],
      },
      boxShadow: {
        'subtle': '0 4px 20px -2px rgba(28, 34, 46, 0.03)',
        'premium': '0 10px 40px -10px rgba(10, 17, 32, 0.08)'
      }
    },
  },
  plugins: [],
}
