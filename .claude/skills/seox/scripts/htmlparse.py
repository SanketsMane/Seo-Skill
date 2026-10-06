"""HTML fact extraction for SEO analysis (stdlib html.parser).

extract(html, base_url) -> dict of facts. No judgments here; page.py turns
facts into checks so the crawler can reuse the same extraction cheaply.
"""

import json
import re
from html.parser import HTMLParser
from urllib import parse

SKIP_TEXT = {"script", "style", "noscript", "template", "svg", "iframe", "object"}
BLOCK_TAGS = {"p", "div", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
              "section", "article", "header", "footer", "nav", "main", "aside",
              "blockquote", "pre", "dd", "dt", "figcaption", "br", "tr", "summary"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
BOILERPLATE = {"nav", "header", "footer", "aside"}


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.skip_depth = 0
        self.boiler_depth = 0
        self.in_head = False
        self.f = {
            "doctype": None, "html_attrs": {}, "titles": [], "metas": [],
            "links": [], "scripts": [], "headings": [], "paragraphs": [],
            "images": [], "anchors": [], "jsonld": [], "iframes": [],
            "picture_sources": [], "itemtypes": [], "rdfa_types": [],
            "semantic": {}, "lists": 0, "list_items": 0, "tables": 0,
            "forms": 0, "element_count": 0, "inline_styles": 0,
            "times": [], "text_chunks": [], "main_text_chunks": [],
            "ids": [], "details": 0, "dl": 0, "videos": 0,
        }
        self._cur_title = None
        self._cur_heading = None
        self._cur_p = None
        self._cur_a = None
        self._cur_script = None
        self._buf = []

    # -- helpers --------------------------------------------------------
    def _text_target(self, data):
        if self._cur_title is not None:
            self._cur_title.append(data)
        if self._cur_heading is not None:
            self._cur_heading["parts"].append(data)
        if self._cur_p is not None:
            self._cur_p.append(data)
        if self._cur_a is not None:
            self._cur_a["parts"].append(data)

    def handle_decl(self, decl):
        self.f["doctype"] = decl

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        f = self.f
        f["element_count"] += 1
        if tag not in VOID:
            self.stack.append(tag)
        if "style" in a:
            f["inline_styles"] += 1
        if a.get("id"):
            f["ids"].append(a["id"])
        if a.get("itemtype"):
            f["itemtypes"].append(a["itemtype"])
        if a.get("typeof"):
            f["rdfa_types"].append(a["typeof"])
        if tag in ("main", "article", "nav", "header", "footer", "aside", "section", "figure"):
            f["semantic"][tag] = f["semantic"].get(tag, 0) + 1
        if tag in BOILERPLATE:
            self.boiler_depth += 1
        if tag in SKIP_TEXT:
            self.skip_depth += 1
        if tag in BLOCK_TAGS:
            f["text_chunks"].append("\n")
            f["main_text_chunks"].append("\n")

        if tag == "html":
            f["html_attrs"] = a
        elif tag == "head":
            self.in_head = True
        elif tag == "body":
            self.in_head = False
        elif tag == "title" and self._cur_title is None and "svg" not in self.stack:
            self._cur_title = []
        elif tag == "meta":
            f["metas"].append(a)
        elif tag == "link":
            a["_in_head"] = self.in_head
            f["links"].append(a)
        elif tag == "script":
            a["_in_head"] = self.in_head
            f["scripts"].append(a)
            if "ld+json" in a.get("type", "").lower():
                self._cur_script = []
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._cur_heading = {"level": int(tag[1]), "parts": [],
                                 "in_boilerplate": self.boiler_depth > 0}
        elif tag == "p":
            self._cur_p = []
        elif tag == "a":
            self._cur_a = {"href": a.get("href"), "rel": a.get("rel", ""),
                           "title": a.get("title", ""), "aria": a.get("aria-label", ""),
                           "target": a.get("target", ""), "parts": [], "img_alts": [],
                           "in_boilerplate": self.boiler_depth > 0,
                           "in_nav": "nav" in self.stack}
        elif tag == "img":
            a["_index"] = len(f["images"])
            a["_in_picture"] = "picture" in self.stack
            a["_in_a"] = self._cur_a is not None
            f["images"].append(a)
            if self._cur_a is not None:
                self._cur_a["img_alts"].append(a.get("alt"))
        elif tag == "source" and "picture" in self.stack:
            f["picture_sources"].append(a)
        elif tag in ("ul", "ol"):
            f["lists"] += 1
        elif tag == "li":
            f["list_items"] += 1
        elif tag == "table":
            f["tables"] += 1
        elif tag == "form":
            f["forms"] += 1
        elif tag == "iframe":
            f["iframes"].append(a)
        elif tag == "time":
            f["times"].append(a.get("datetime", ""))
        elif tag == "details":
            f["details"] += 1
        elif tag == "dl":
            f["dl"] += 1
        elif tag == "video":
            f["videos"] += 1

    def handle_endtag(self, tag):
        f = self.f
        if tag in self.stack:
            while self.stack:
                t = self.stack.pop()
                if t in SKIP_TEXT:
                    self.skip_depth = max(0, self.skip_depth - 1)
                if t in BOILERPLATE:
                    self.boiler_depth = max(0, self.boiler_depth - 1)
                if t == tag:
                    break
        if tag == "title" and self._cur_title is not None:
            f["titles"].append(_clean("".join(self._cur_title)))
            self._cur_title = None
        elif tag == "script" and self._cur_script is not None:
            f["jsonld"].append("".join(self._cur_script))
            self._cur_script = None
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._cur_heading:
            h = self._cur_heading
            f["headings"].append({"level": h["level"], "text": _clean("".join(h["parts"])),
                                  "in_boilerplate": h["in_boilerplate"]})
            self._cur_heading = None
        elif tag == "p" and self._cur_p is not None:
            txt = _clean("".join(self._cur_p))
            if txt:
                f["paragraphs"].append(txt)
            self._cur_p = None
        elif tag == "a" and self._cur_a is not None:
            al = self._cur_a
            al["text"] = _clean("".join(al.pop("parts")))
            f["anchors"].append(al)
            self._cur_a = None
        if tag in BLOCK_TAGS:
            f["text_chunks"].append("\n")
            f["main_text_chunks"].append("\n")

    def handle_data(self, data):
        if self._cur_script is not None:
            self._cur_script.append(data)
            return
        if self._cur_title is not None:
            self._cur_title.append(data)
            return
        if self.skip_depth:
            return
        self._text_target(data)
        self.f["text_chunks"].append(data)
        if not self.boiler_depth:
            self.f["main_text_chunks"].append(data)


def _clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _join_text(chunks):
    txt = "".join(chunks)
    lines = [_clean(l) for l in txt.split("\n")]
    return "\n".join(l for l in lines if l)


def _meta_map(metas):
    out = {}
    for m in metas:
        key = (m.get("name") or m.get("property") or m.get("http-equiv") or "").lower()
        if key:
            out.setdefault(key, []).append(m.get("content", ""))
    return out


def classify_link(href, base_url):
    if href is None:
        return None, "missing-href"
    href = href.strip()
    if not href:
        return None, "empty-href"
    low = href.lower()
    if low.startswith("javascript:"):
        return None, "javascript"
    if low.startswith(("mailto:", "tel:", "sms:", "data:")):
        return None, low.split(":", 1)[0]
    if href.startswith("#"):
        return None, "fragment"
    absu = parse.urljoin(base_url, href)
    absu = parse.urldefrag(absu)[0]
    if not absu.startswith(("http://", "https://")):
        return None, "other-scheme"
    bh = parse.urlsplit(base_url).netloc.lower()
    lh = parse.urlsplit(absu).netloc.lower()
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return absu, ("internal" if strip(bh) == strip(lh) else "external")


def extract(html, base_url):
    p = _Parser()
    try:
        p.feed(html)
        p.close()
    except Exception as e:  # malformed markup should never kill an audit
        p.f["parse_error"] = str(e)
    f = p.f
    metas = _meta_map(f["metas"])

    base = base_url
    m = re.search(r"<base[^>]+href=[\"']([^\"']+)", html[:20000], re.I)
    if m:
        base = parse.urljoin(base_url, m.group(1))

    def rel_has(l, val):
        return val in (l.get("rel", "").lower().split())

    canonicals = [l.get("href", "") for l in f["links"] if rel_has(l, "canonical")]
    hreflangs = [{"hreflang": l.get("hreflang", ""), "href": parse.urljoin(base, l.get("href", "")),
                  "in_head": l.get("_in_head")}
                 for l in f["links"] if rel_has(l, "alternate") and l.get("hreflang")]

    jsonld_blocks = []
    for raw in f["jsonld"]:
        raw_s = raw.strip()
        try:
            jsonld_blocks.append({"ok": True, "data": json.loads(raw_s)})
        except ValueError as e:
            jsonld_blocks.append({"ok": False, "error": str(e), "raw": raw_s[:500]})

    anchors = []
    for a in f["anchors"]:
        absu, kind = classify_link(a["href"], base)
        rels = set(a["rel"].lower().split())
        accessible = a["text"] or a["aria"] or " ".join(x for x in a["img_alts"] if x) or a["title"]
        anchors.append({
            "href": a["href"], "url": absu, "kind": kind, "text": a["text"],
            "accessible_name": _clean(accessible), "nofollow": "nofollow" in rels,
            "sponsored": "sponsored" in rels, "ugc": "ugc" in rels,
            "in_boilerplate": a["in_boilerplate"], "in_nav": a["in_nav"],
        })

    images = []
    for im in f["images"]:
        src = im.get("src") or im.get("data-src") or im.get("data-lazy-src") or ""
        images.append({
            "src": parse.urljoin(base, src) if src and not src.startswith("data:") else src[:60],
            "alt": im.get("alt"), "has_alt_attr": "alt" in im,
            "width": im.get("width"), "height": im.get("height"),
            "loading": (im.get("loading") or "").lower(),
            "decoding": im.get("decoding"), "fetchpriority": (im.get("fetchpriority") or "").lower(),
            "srcset": bool(im.get("srcset") or im.get("data-srcset")),
            "sizes": im.get("sizes"), "role": im.get("role"),
            "aria_hidden": im.get("aria-hidden") == "true",
            "lazy_js": bool(im.get("data-src") or im.get("data-lazy-src")) and not im.get("src"),
            "in_picture": im["_in_picture"], "in_link": im["_in_a"], "index": im["_index"],
            "style_has_aspect": "aspect-ratio" in (im.get("style") or ""),
        })

    text = _join_text(f["text_chunks"])
    main_text = _join_text(f["main_text_chunks"])

    head_scripts = [s for s in f["scripts"] if s.get("_in_head")]
    render_blocking_js = [s.get("src") for s in head_scripts
                          if s.get("src") and "async" not in s and "defer" not in s
                          and s.get("type", "").lower() not in ("module", "application/ld+json")]
    stylesheets = [l.get("href") for l in f["links"] if rel_has(l, "stylesheet")]
    blocking_css = [l.get("href") for l in f["links"] if rel_has(l, "stylesheet")
                    and l.get("_in_head") and (l.get("media", "all") in ("", "all", "screen"))]
    preloads = [{"href": l.get("href"), "as": l.get("as"), "fetchpriority": l.get("fetchpriority")}
                for l in f["links"] if rel_has(l, "preload")]

    return {
        "doctype": f["doctype"],
        "lang": f["html_attrs"].get("lang"),
        "dir": f["html_attrs"].get("dir"),
        "titles": f["titles"],
        "title": f["titles"][0] if f["titles"] else None,
        "meta": metas,
        "meta_description": (metas.get("description") or [None])[0],
        "meta_robots": metas.get("robots", []) + metas.get("googlebot", []),
        "meta_robots_by_bot": {k: v for k, v in metas.items()
                               if k in ("robots", "googlebot", "bingbot", "googlebot-news")},
        "viewport": (metas.get("viewport") or [None])[0],
        "charset": next((m.get("charset") for m in f["metas"] if m.get("charset")), None)
                   or (metas.get("content-type") or [None])[0],
        "canonicals": canonicals,
        "canonical_in_body": [l.get("href") for l in f["links"]
                              if rel_has(l, "canonical") and not l.get("_in_head")],
        "hreflang": hreflangs,
        "og": {k: v[0] for k, v in metas.items() if k.startswith("og:")},
        "twitter": {k: v[0] for k, v in metas.items() if k.startswith("twitter:")},
        "article_meta": {k: v[0] for k, v in metas.items() if k.startswith("article:")},
        "author_meta": (metas.get("author") or [None])[0],
        "headings": f["headings"],
        "paragraphs": f["paragraphs"],
        "text": text,
        "main_text": main_text,
        "word_count": len(re.findall(r"\b[\w'-]+\b", text, re.U)),
        "main_word_count": len(re.findall(r"\b[\w'-]+\b", main_text, re.U)),
        "images": images,
        "picture_sources": [{"type": s.get("type"), "srcset": (s.get("srcset") or "")[:120]}
                            for s in f["picture_sources"]],
        "anchors": anchors,
        "jsonld": jsonld_blocks,
        "microdata_types": f["itemtypes"],
        "rdfa_types": f["rdfa_types"],
        "semantic": f["semantic"],
        "lists": f["lists"], "list_items": f["list_items"], "tables": f["tables"],
        "details": f["details"], "definition_lists": f["dl"], "videos": f["videos"],
        "forms": f["forms"], "iframes": [i.get("src") for i in f["iframes"]],
        "element_count": f["element_count"], "inline_styles": f["inline_styles"],
        "times": f["times"],
        "scripts_total": len(f["scripts"]),
        "scripts_external": len([s for s in f["scripts"] if s.get("src")]),
        "render_blocking_js": render_blocking_js,
        "stylesheets": stylesheets,
        "render_blocking_css": blocking_css,
        "preloads": preloads,
        "duplicate_ids": sorted({i for i in f["ids"] if f["ids"].count(i) > 1})[:20],
        "parse_error": f.get("parse_error"),
    }
