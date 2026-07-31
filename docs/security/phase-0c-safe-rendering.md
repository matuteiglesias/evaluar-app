# Phase 0C: safe rendering

## Trust boundaries and inventory

Exercise `.tex` files and `index.csv` metadata are repository content, not trusted
HTML. Student answers influence model output, so model Markdown is also untrusted.
Student feedback, teacher questions, OAuth profile values, and ticket/session values
remain ordinary Jinja values and are autoescaped.

The rendering inventory found two Jinja `safe` filters, Markdown conversion in the
answer route, LaTeX-to-HTML compatibility substitutions, metadata interpolation
through two JavaScript `innerHTML` assignments, and duplicated unused browser
Firebase initialization in the exercise, index, and feedback templates. The safe
filters, dynamic `innerHTML`, and browser Firebase initialization were removed.
Ticket download data now uses Jinja's context-aware `tojson` result directly rather
than parsing a quoted `safe` string.

## Allowlists

`services.safe_rendering` is the only boundary that produces trusted `Markup`.

- Exercise compatibility output permits `p`, `br`, `em`, `i`, `strong`, `ol`,
  `ul`, `li`, `pre`, `code`, `div`, and `img`. A `div` may only have the
  `exercise-center` class. An image may only have `alt`, the `exercise-figure`
  class, and a source matching `/tikzpics/[A-Za-z0-9_-]+.png`. No style, event,
  iframe, SVG, link, or external URL is retained.
- TeX commands capable of producing links or HTML attributes (`href`, `url`,
  `class`, `style`, `cssId`, the `html*` family, and `unicode`) are neutralized
  to visibly inert full-width slash text before MathJax can process them.
- Model feedback permits `p`, `br`, `em`, `strong`, `ol`, `ul`, `li`, `pre`,
  `code`, and `blockquote`, with no attributes or URL-bearing elements. Markdown
  uses only the explicit `fenced_code` and `sane_lists` extensions before Bleach
  sanitization.

Bleach strips disallowed markup and comments. Jinja recognizes only the `Markup`
instances returned after cleaning; templates no longer override escaping with
`safe`. Course metadata is inserted into DOM nodes with `textContent`; exercise
links are assembled from validated fields with explicit URL-component encoding.

## Deliberate limitations and residual risks

- Repository-authored arbitrary HTML, inline styling, links, SVG, and remote
  images are intentionally not supported. Unsupported constructs become text or
  are removed.
- Math remains text for MathJax processing. Sanitization does not attempt to parse
  TeX semantics; MathJax must remain maintained and securely configured.
- Existing third-party script and stylesheet CDNs are outside this phase's output
  sanitization boundary. A later phase should address supply-chain policy and CSP.
- Sanitization is defense in depth, not permission to accept unreviewed repository
  content. Regression tests cover scripts, event handlers, SVG, unsafe URLs,
  malformed nesting, raw Markdown HTML, and reflected question content.
