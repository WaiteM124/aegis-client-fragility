/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        base: '#0a0f1e',
        card: 'rgba(30,41,59,0.5)',
      },
    },
  },
  plugins: [],
}
