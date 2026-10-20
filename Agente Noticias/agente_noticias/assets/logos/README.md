# Company logos (card badge)

Transparent PNGs, 128 px tall, named `<key>.png` with the canonical keys of
`schemas.CompanyKey` / `logos.COMPANY_DISPLAY_NAMES`. The badge scales them to 36 px
(at 2x) next to the company name. If a file is missing, the badge shows the name only.

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

To add a company: add the key to `schemas.CompanyKey` and `logos.COMPANY_DISPLAY_NAMES`
and drop a `<key>.png` here (transparent, ~128 px tall, symbol only — the name is drawn
by the badge).
