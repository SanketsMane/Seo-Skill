#!/usr/bin/env python3
"""Detect a codebase's framework and locate SEO-relevant files.

Usage:
  detect_stack.py [path]

Outputs framework, router/rendering hints and the files that control
metadata, sitemap, robots, structured data, images, redirects and headers,
so the fix module knows where to edit instead of guessing.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import emit  # noqa: E402

IGNORE = {"node_modules", ".git", ".next", "dist", "build", ".nuxt", ".output", ".astro", "vendor",
          ".svelte-kit", "coverage", ".turbo", ".vercel", "__pycache__", ".venv", "venv"}
PATTERNS = {
    "metadata": r"(generateMetadata|export const metadata|useHead|useSeoMeta|<Helmet|next/head|<svelte:head>|wp_head|<title>|\bSEO\b\s*\(|head\(\)\s*{)",
    "jsonld": r"application/ld\+json",
    "sitemap": r"(sitemap)",
    "robots": r"(robots\.(txt|ts|js)|MetadataRoute\.Robots|noindex)",
    "canonical": r"(rel=[\"']canonical|alternates\s*:\s*{|canonical\s*:)",
    "image_component": r"(next/image|<Image\b|<NuxtImg|<img\b|astro:assets)",
    "redirects": r"(redirects\s*\(|_redirects|\"redirects\"|return\s+redirect|RewriteRule|permanentRedirect)",
    "hreflang": r"(hreflang|alternates\s*:\s*{\s*languages|i18n)",
}
EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".astro", ".svelte", ".php", ".html", ".njk",
       ".liquid", ".hbs", ".erb", ".py", ".json", ".toml", ".yaml", ".yml", ".conf", ".htaccess", ".txt", ".xml")


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    pkg = {}
    pj = os.path.join(root, "package.json")
    if os.path.exists(pj):
        try:
            pkg = json.load(open(pj))
        except ValueError:
            pkg = {}
    deps = dict(pkg.get("dependencies", {}), **pkg.get("devDependencies", {}))
    exists = lambda *p: os.path.exists(os.path.join(root, *p))
    fw = []
    if "next" in deps:
        router = "app" if (exists("app") or exists("src", "app")) else "pages"
        fw.append("Next.js %s (%s router)" % (deps["next"], router))
    for name, label in (("nuxt", "Nuxt"), ("astro", "Astro"), ("@sveltejs/kit", "SvelteKit"), ("gatsby", "Gatsby"),
                        ("@remix-run/react", "Remix"), ("react-router", "React Router"), ("@angular/core", "Angular"),
                        ("vue", "Vue"), ("react", "React"), ("vite", "Vite"), ("express", "Express"), ("@11ty/eleventy", "Eleventy")):
        if name in deps and not any(label in f for f in fw):
            fw.append("%s %s" % (label, deps[name]))
    if exists("wp-config.php") or exists("wp-content"):
        fw.append("WordPress")
    if exists("artisan"):
        fw.append("Laravel")
    if exists("composer.json") and not fw:
        fw.append("PHP (composer)")
    if exists("hugo.toml") or exists("config.toml") and exists("content"):
        fw.append("Hugo (probable)")
    if exists("_config.yml") and exists("_layouts"):
        fw.append("Jekyll")
    if exists("manage.py"):
        fw.append("Django")
    hits = {k: [] for k in PATTERNS}
    special = []
    count = 0
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in IGNORE and not x.startswith(".") or x in (".htaccess",)]
        for fn in files:
            rel = os.path.relpath(os.path.join(d, fn), root)
            if re.search(r"(^|/)(sitemap(\.xml)?\.(ts|js|xml|mjs)|robots\.(ts|js|txt)|llms\.txt|_redirects|_headers|vercel\.json|netlify\.toml|\.htaccess|nginx\.conf|next\.config\.\w+|nuxt\.config\.\w+|astro\.config\.\w+|middleware\.(ts|js)|manifest\.(ts|json|webmanifest))$", rel):
                special.append(rel)
            if not fn.endswith(EXT) or fn.endswith((".min.js", ".lock")) or fn == "package-lock.json":
                continue
            count += 1
            if count > 6000:
                break
            try:
                with open(os.path.join(d, fn), encoding="utf-8", errors="ignore") as fh:
                    txt = fh.read(300000)
            except OSError:
                continue
            for k, rx in PATTERNS.items():
                if k == "sitemap" and "sitemap" not in fn.lower() and "sitemap" not in txt[:5000].lower():
                    continue
                if re.search(rx, txt) and len(hits[k]) < 40:
                    hits[k].append(rel)
    layouts = [x for x in hits["metadata"] if re.search(r"(layout|_app|_document|head|seo|app\.vue|Layout)", x, re.I)]
    scripts = pkg.get("scripts", {})
    emit({"root": root, "frameworks": fw or ["static/unknown"], "package_manager":
          "pnpm" if exists("pnpm-lock.yaml") else "yarn" if exists("yarn.lock") else "bun" if exists("bun.lockb") else "npm" if exists("package-lock.json") else None,
          "scripts": {k: v for k, v in scripts.items() if k in ("build", "dev", "start", "lint", "test", "typecheck", "preview")},
          "special_files": sorted(special), "likely_layouts": layouts[:15], "files_by_concern": hits,
          "files_scanned": count})


if __name__ == "__main__":
    main()
