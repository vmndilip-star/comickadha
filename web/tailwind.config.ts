import type { Config } from 'tailwindcss'

/**
 * Theme names for the "Sunday Funnies" design system.
 * Values live in src/styles/tokens.css; this file only maps Tailwind names to those variables.
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'var(--ck-ink)',
        paper: 'var(--ck-paper)',
        surface: 'var(--ck-surface)',
        sun: { DEFAULT: 'var(--ck-sun)', tint: 'var(--ck-sun-tint)', dot: 'var(--ck-sun-dot)' },
        'pow-blue': 'var(--ck-pow-blue)',
        'zap-coral': {
          DEFAULT: 'var(--ck-zap-coral)',
          light: 'var(--ck-coral-light)',
          tint: 'var(--ck-coral-tint)',
        },
        mint: 'var(--ck-mint)',
        sky: { DEFAULT: 'var(--ck-sky)', tint: 'var(--ck-sky-tint)' },
        muted: 'var(--ck-muted)',
        rule: 'var(--ck-rule)',
      },
      fontFamily: {
        display: ['Bangers', 'cursive'],
        body: ['Nunito', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'display-xl': ['64px', { lineHeight: '1', letterSpacing: '1px' }],
        h1: ['52px', { lineHeight: '1', letterSpacing: '1px' }],
        h2: ['34px', { lineHeight: '1.1', letterSpacing: '1px' }],
        h3: ['28px', { lineHeight: '1.1', letterSpacing: '1px' }],
        title: ['22px', { lineHeight: '1.3' }],
        label: ['14px', { lineHeight: '1.4' }],
      },
      borderRadius: {
        button: 'var(--ck-radius-button)',
        tile: 'var(--ck-radius-tile)',
        card: 'var(--ck-radius-card)',
        hero: 'var(--ck-radius-hero)',
        pill: 'var(--ck-radius-pill)',
      },
      boxShadow: {
        sm: 'var(--ck-shadow-sm)',
        card: 'var(--ck-shadow-card)',
        hero: 'var(--ck-shadow-hero)',
        'hero-lg': 'var(--ck-shadow-hero-lg)',
        selected: '5px 5px 0 var(--ck-pow-blue)',
        'tile-selected': '4px 4px 0 var(--ck-pow-blue)',
      },
      maxWidth: { content: 'var(--ck-max-width)' },
      minHeight: { touch: 'var(--ck-touch)' },
      minWidth: { touch: 'var(--ck-touch)' },
    },
  },
} satisfies Config
