/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
          950: "#1e1b4b",
        },
      },
      boxShadow: {
        soft: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 8px 24px -8px rgb(79 70 229 / 0.12)",
        card: "0 1px 3px 0 rgb(15 23 42 / 0.06), 0 12px 32px -12px rgb(15 23 42 / 0.10)",
        "card-hover": "0 2px 6px 0 rgb(15 23 42 / 0.06), 0 24px 48px -16px rgb(79 70 229 / 0.22)",
        glow: "0 10px 40px -10px rgb(99 102 241 / 0.5)",
        "glow-lg": "0 16px 60px -12px rgb(99 102 241 / 0.55)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #d946ef 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, #eef2ff 0%, #faf5ff 100%)",
        "brand-gradient-animated":
          "linear-gradient(135deg, #4338ca 0%, #6366f1 25%, #7c3aed 50%, #d946ef 75%, #6366f1 100%)",
        shimmer:
          "linear-gradient(90deg, rgba(226,232,240,0) 0%, rgba(226,232,240,0.85) 50%, rgba(226,232,240,0) 100%)",
        "grid-slate":
          "linear-gradient(to right, rgb(226 232 240 / 0.5) 1px, transparent 1px), linear-gradient(to bottom, rgb(226 232 240 / 0.5) 1px, transparent 1px)",
      },
      backgroundSize: {
        "size-200": "200% 200%",
        grid: "32px 32px",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(12px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "gradient-pan": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        "bounce-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.5" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in": "fade-in 0.3s ease-out both",
        "scale-in": "scale-in 0.25s cubic-bezier(0.16, 1, 0.3, 1) both",
        "slide-in-right": "slide-in-right 0.35s cubic-bezier(0.16, 1, 0.3, 1) both",
        shimmer: "shimmer 1.6s ease-in-out infinite",
        "gradient-pan": "gradient-pan 6s ease infinite",
        "pulse-soft": "pulse-soft 2s ease-in-out infinite",
        float: "float 5s ease-in-out infinite",
        "bounce-dot": "bounce-dot 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
}
