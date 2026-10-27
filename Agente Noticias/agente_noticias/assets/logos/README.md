# Company logos (card badge)

Built-in logos of the 14 key companies: transparent PNGs, 128 px tall, named
`<key>.png` with the keys of `logos.COMPANY_DISPLAY_NAMES` (`schemas.CompanyKey`). The
badge scales them to 36 px (at 2x) next to the company name. Any other company gets its
logo learned at runtime (see below); if none is found, the badge shows the name only.

All files are server-side PNG renders of SVGs on Wikimedia Commons (downloaded
2026-10-20), trimmed to their visible area and resized. Trademarks belong to their owners;
they are used only to identify the company each news item is about.

| Key | Commons file | Notes |
| --- | --- | --- |
| openai | `File:OpenAI logo 2025 (symbol).svg` | |
| anthropic | `File:Claude AI symbol.svg` | Claude spark (Anthropic's wordmark is text-only) |
| google | `File:Google "G" logo.svg` | |
| gemini | `File:Google Gemini icon 2025.svg` | |
| meta | `File:Meta Platforms Inc. logo (cropped).svg` | |
| microsoft | `File:Microsoft logo (2012).svg` | four squares only (wordmark removed) |
| nvidia | `File:NVIDIA logo.svg` | green eye only (wordmark removed) |
| xai | `File:XAI-Logo.svg` | |
| mistral | `File:Mistral AI logo (2025–).svg` | |
| deepseek | `File:Deepseek-logo-icon.svg` | |
| apple | `File:Apple logo black.svg` | |
| amazon | `File:Amazon icon.svg` | |
| qwen | `File:Qwen logo.svg` | |
| alibaba | `File:AlibabaCloudLogo.svg` | bracket icon only (wordmark removed) |

To add a key company: add the key to `schemas.CompanyKey` and
`logos.COMPANY_DISPLAY_NAMES` (plus aliases in `logos._ALIASES`) and drop a `<key>.png`
here (transparent, ~128 px tall, symbol only — the name is drawn by the badge).

## Learned logos (`data/logos/`, not versioned)

`logo_finder.ensure_logo` fills the gaps: a LangChain agent picks the company's Wikidata
item, then deterministic code downloads its P8972 (small logo or icon) or P154 (logo
image) file as a PNG render from Wikimedia Commons (`Special:FilePath/<file>?width=512`),
trims transparent/white margins, scales it to 128 px tall and saves
`data/logos/<slug>.png`. `data/logos/registry.json` records, per slug, the display name,
Wikidata QID, property, Commons file name, source URL, file page (author and license are
on that page) and `saved_at`; misses are stored as `not_found` with `checked_at` and are
not retried for 30 days. To fix a wrong logo, delete its PNG and registry entry (or drop
a corrected `<slug>.png` there).

Badge rules: symbol logo + name; a wordmark (width/height >= 2.6) is drawn alone; no
logo -> name only.

Logos are trademarks of their owners. Like the built-in ones, learned logos are used
only for editorial identification of the company each news item is about; check the
Commons file page before any other use.
