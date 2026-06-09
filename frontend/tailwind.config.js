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
        // Premium "Graphite & Amber" palette. `brand` is a warm amber accent;
        // graphite (dark warm-neutral) is used for chrome / dark surfaces.
        brand: {
          50: "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          300: "#fcd34d",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
          800: "#92400e",
          900: "#78350f",
          950: "#451a03",
        },
        graphite: {
          50: "#f7f7f6",
          100: "#e6e5e3",
          200: "#cfcdc9",
          300: "#a9a6a0",
          400: "#7d7a73",
          500: "#5c5953",
          600: "#403d38",
          700: "#33312d",
          800: "#26241f",
          900: "#1a1815",
          950: "#0f0e0c",
        },
      },
      boxShadow: {
        soft: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 8px 24px -8px rgb(180 83 9 / 0.12)",
        card: "0 1px 3px 0 rgb(15 23 42 / 0.06), 0 12px 32px -12px rgb(15 23 42 / 0.10)",
        "card-hover": "0 2px 6px 0 rgb(15 23 42 / 0.06), 0 24px 48px -16px rgb(180 83 9 / 0.22)",
        glow: "0 10px 40px -10px rgb(217 119 6 / 0.45)",
        "glow-lg": "0 16px 60px -12px rgb(217 119 6 / 0.5)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #f59e0b 0%, #d97706 55%, #b45309 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)",
        "brand-gradient-animated":
          "linear-gradient(135deg, #92400e 0%, #b45309 25%, #d97706 50%, #f59e0b 75%, #d97706 100%)",
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
