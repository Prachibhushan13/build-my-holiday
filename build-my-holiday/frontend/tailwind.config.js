/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"] },
      colors: { brand: { 50: "#eef5ff", 100: "#d9e8ff", 500: "#2f6fed", 600: "#2258d1", 700: "#1d47a8", 900: "#12254f" } },
    },
  },
  plugins: [],
};
