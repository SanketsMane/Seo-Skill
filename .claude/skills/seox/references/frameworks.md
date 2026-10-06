# Framework Implementation Playbooks

Always: read the existing implementation first, follow its patterns, change the narrowest layer that fixes the issue (shared layout/template over per-page), keep diffs minimal, then build.

## Next.js — App Router
- **Metadata**: `export const metadata` (static) or `export async function generateMetadata({ params })` in `layout.tsx`/`page.tsx`. Set `metadataBase: new URL('https://example.com')` in the root layout so relative canonicals/OG URLs resolve. Title templates: `title: { default: 'Brand', template: '%s | Brand' }`.
- **Canonical / hreflang**: `alternates: { canonical: '/path', languages: { 'en-US': '/en-us/path', 'x-default': '/path' } }`.
- **Robots meta**: `robots: { index: false, follow: true }` per route.
- **OG/Twitter**: `openGraph`, `twitter` fields, or `opengraph-image.tsx` file convention.
- **Sitemap**: `app/sitemap.ts` returning `MetadataRoute.Sitemap`; split with `generateSitemaps` for >50k URLs. Only include canonical, indexable URLs; use real `lastModified`.
- **Robots**: `app/robots.ts` returning `MetadataRoute.Robots` with `sitemap`.
- **JSON-LD**: render `<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, '\\u003c') }} />` in the page component (server component).
- **Static/dynamic**: `generateStaticParams` for SSG of dynamic routes; avoid client-only data fetching for indexable content (`'use client'` + `useEffect` fetch = invisible to non-rendering crawlers).
- **Images**: `next/image` with explicit `width`/`height` or `fill` + sized container; `priority` (or `fetchPriority="high"` in newer versions) on the LCP image; descriptive `alt`.
- **Redirects**: `redirects()` in `next.config.*` with `permanent: true`, or `permanentRedirect()` in route code; `middleware.ts` for host/locale logic.
- **404s**: `notFound()` in dynamic routes for missing data (prevents soft 404s).

## Next.js — Pages Router
`next/head` per page (or a shared `<Seo>` component); `getStaticProps`/`getServerSideProps` for content; sitemap via a route (`pages/sitemap.xml.ts`) or build script; `public/robots.txt`. Watch for duplicate `<title>` from `_app` + page.

## React SPA (Vite/CRA)
Biggest risk is client-only rendering. Options in order: migrate key pages to SSR/SSG (Next/Remix/Astro), prerender static routes (e.g. vite prerender plugin), at minimum server-inject per-route title/description/canonical. `react-helmet-async` only helps crawlers that render. Configure the host to return real 404 status for unknown routes.

## Nuxt 3
`useSeoMeta({ title, description, ogImage })`, `useHead({ link: [{ rel: 'canonical', href }] , script: [{ type: 'application/ld+json', innerHTML: JSON.stringify(data) }] })`; `app.head` defaults in `nuxt.config`. Modules commonly used: `@nuxtjs/sitemap`, `@nuxtjs/robots` (check if installed before adding). `routeRules` for prerender/redirects.

## Vue (Vite SPA)
Same risks as React SPA; `@unhead/vue` for head management; prerender or move to Nuxt for content pages.

## Astro
Head tags in a shared `BaseLayout.astro` taking `title`, `description`, `canonical` props; `Astro.site` + `Astro.url.pathname` for canonicals (set `site` in `astro.config`). `@astrojs/sitemap` integration. `<Image />` from `astro:assets` for sizes/formats. JSON-LD via `<script type="application/ld+json" set:html={JSON.stringify(data)} />`.

## SvelteKit
`<svelte:head>` in `+page.svelte`/`+layout.svelte`; data from `+page.server.ts`; `prerender = true` where possible; sitemap via `src/routes/sitemap.xml/+server.ts`.

## WordPress
Check active SEO plugin first (Yoast, Rank Math, SEOPress, AIOSEO) — configure it rather than hand-coding duplicates. Theme edits go in a child theme. `wp_head` hooks for custom tags; core sitemap at `/wp-sitemap.xml` (plugins replace it). Watch for duplicate titles/canonicals from theme + plugin, `noindex` left on from staging (Settings → Reading → "Discourage search engines").

## PHP / Laravel
Shared Blade layout with `@yield('title')`/`@section`, or a meta component; packages like `artesaninc/seotools` or `spatie/laravel-sitemap` (check composer.json before adding). Redirects in routes (`Route::permanentRedirect`) or web server config.

## Node / Express
Template engine layout receives `title/description/canonical` per route; `res.redirect(301, ...)`; set `X-Robots-Tag` header for non-HTML assets if needed; `compression` middleware; real 404 handler.

## Static HTML
Edit each page's `<head>`; consistent shared partial if a generator is used; hand-written `sitemap.xml` (or generate from crawl with `sitemap.py generate`); server config (`.htaccess`, `nginx.conf`, `_redirects`, `vercel.json`, `netlify.toml`) for redirects/headers.

## Server/CDN-level fixes (any stack)
HTTPS + host redirects, compression (gzip/brotli), caching headers, HSTS/security headers, HTTP/2/3 — usually CDN or web-server config, not app code. Tell the user where the change lives if it's outside the repo.
