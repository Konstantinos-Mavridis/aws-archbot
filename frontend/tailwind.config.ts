import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        brand: {
          50:  '#f0fafa',
          100: '#cceff0',
          200: '#99dfe2',
          300: '#5fc9ce',
          400: '#2dadb4',
          500: '#01696f',
          600: '#0c4e54',
          700: '#0f3638',
          800: '#0d2426',
          900: '#091617',
        },
      },
    },
  },
  plugins: [],
}
export default config
