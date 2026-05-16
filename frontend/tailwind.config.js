/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1A6B3C',
        secondary: '#C9A84C',
        dark: '#2C3E50',
        light: '#E8F5E9',
      }
    },
  },
  plugins: [],
}
