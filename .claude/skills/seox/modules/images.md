# /seox images <url> — Image SEO

## Run
`page.py <url> --image-sizes 40 > $D/images.json` (repeat for key templates). `facts.images` lists every image with alt, dimensions, loading, fetchpriority, srcset, format.

## Evaluate
- **Alt text**: missing attribute (FAIL for informative images), `alt=""` (correct for decorative), weak (filenames, generic words, keyword lists, >150 chars), linked images without alt (the alt is the link text).
- **Filenames**: descriptive, hyphenated (`blue-trail-running-shoe.jpg` vs `IMG_4032.jpg`) — low priority, only for new uploads.
- **Format**: WebP/AVIF for photos (CDNs may negotiate by `Accept` — confirm with `curl -sI -H 'Accept: image/avif,image/webp' <img>` before flagging); SVG for icons/logos.
- **Weight**: >250 KB warn, >600 KB serious, relative to display size.
- **Responsive**: `srcset`/`sizes` or `<picture>`; no 2000px images in 300px slots.
- **CLS**: width/height or aspect-ratio on every image.
- **Loading**: LCP/hero image not lazy, ideally `fetchpriority="high"`; below-the-fold images `loading="lazy"`.
- **Discoverability**: important images in `<img>` (not CSS backgrounds) if they should appear in Google Images; image sitemap only for large image-led sites.

## Generate alt text
Only describe what you can actually see. If you can't view the image (Read it after downloading to the scratchpad, or ask), write `[PLACEHOLDER: describe image]` rather than guessing from the filename. Alt text describes the image's content and purpose in context, ~5–20 words, no "image of", no keyword lists. Decorative → `alt=""`.

Output a table: image · issue · current alt · proposed alt · action.
