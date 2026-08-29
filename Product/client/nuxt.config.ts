// https://nuxt.com/docs/api/configuration/nuxt-config
import { createRequire } from 'node:module'

const _require = createRequire(import.meta.url)
let _pkgVersion = '0.7.96'
try {
  _pkgVersion = _require('./package.json').version || _pkgVersion
} catch {
  // fallback remains
}

export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  ssr: false,

  css: [
    '@fortawesome/fontawesome-free/css/all.min.css',
    '~/assets/styles/main.scss',
  ],

  experimental: {
    appManifest: false,
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8100',
      appVersion: process.env.NUXT_PUBLIC_APP_VERSION || _pkgVersion,
    },
  },

  app: {
    head: {
      title: 'Power Choice Pro',
      meta: [
        { name: 'description', content: 'A collaborative decision workspace for choices that deserve clarity.' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@600;700;800&family=JetBrains+Mono:wght@400;600&display=swap',
        },
      ],
    },
  },

  vuetify: {
    moduleOptions: {
      styles: { configFile: 'assets/styles/settings.scss' },
    },
    vuetifyOptions: {
      theme: {
        defaultTheme: 'light',
        themes: {
          light: {
            dark: false,
            colors: {
              primary: '#4059D8',
              secondary: '#6F7FF2',
              accent: '#6F7FF2',
              success: '#14967F',
              error: '#C84256',
              warning: '#B56A0A',
              info: '#2F7BC4',
              background: '#F4F6FA',
              surface: '#FFFFFF',
              'on-primary': '#ffffff',
              'on-surface': '#152033',
            },
          },
          dark: {
            dark: true,
            colors: {
              primary: '#7587F4',
              secondary: '#9AA7FF',
              accent: '#9AA7FF',
              success: '#32B69E',
              error: '#E06B7C',
              warning: '#D4923A',
              info: '#5BA3DB',
              background: '#101522',
              surface: '#181F2E',
              'on-primary': '#ffffff',
              'on-surface': '#EDF1FA',
            },
          },
        },
      },
      defaults: {
        VBtn: {
          rounded: 'lg',
          elevation: 0,
        },
        VCard: {
          rounded: 'lg',
          elevation: 0,
        },
        VTextField: {
          variant: 'outlined',
          density: 'comfortable',
          color: 'primary',
        },
        VSelect: {
          variant: 'outlined',
          density: 'comfortable',
          color: 'primary',
        },
        VTextarea: {
          variant: 'outlined',
          density: 'comfortable',
          color: 'primary',
        },
        VSwitch: {
          color: 'primary',
          density: 'comfortable',
        },
        VCheckbox: {
          color: 'primary',
          density: 'comfortable',
        },
        VChip: {
          rounded: 'pill',
        },
      },
    },
  },

  modules: [
    'vuetify-nuxt-module',
    (_options, nuxt) => {
      if (!nuxt.options.dev) return
      nuxt.hook('vite:configResolved', (config) => {
        const ensureEntry = (input: unknown) => {
          if (input && typeof input === 'object' && !Array.isArray(input)) {
            const obj = input as Record<string, string>
            if (obj.entry && !obj.server) obj.server = obj.entry
          }
        }
        ensureEntry(config.build?.rollupOptions?.input)
        const environments = (config as { environments?: Record<string, { build?: { rollupOptions?: { input?: unknown } } }> }).environments
        if (environments) {
          for (const env of Object.values(environments)) {
            ensureEntry(env?.build?.rollupOptions?.input)
          }
        }
      })
    },
  ],

  vite: {
    server: {
      proxy: {
        '/auth-ws': { target: 'http://localhost:8100', changeOrigin: true },
        '/ws': { target: 'http://localhost:8100', changeOrigin: true },
        '/ext-ws': { target: 'http://localhost:8100', changeOrigin: true },
        '/api': { target: 'http://localhost:8100', changeOrigin: true },
        '/status': { target: 'http://localhost:8100', changeOrigin: true },
      },
    },
  },
})
