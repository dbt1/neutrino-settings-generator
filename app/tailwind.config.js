/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        neutrino: {
          primary: "#1d4ed8",
          secondary: "#0f172a",
          accent: "#22d3ee"
        }
      }
    }
  },
  plugins: []
};
