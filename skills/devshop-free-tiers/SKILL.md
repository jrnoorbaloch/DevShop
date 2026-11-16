---
name: devshop-free-tiers
description: Find SaaS, PaaS, IaaS and API services with genuine free tiers for developers (hosting, databases, CI/CD, auth, email, monitoring, AI APIs and 50+ more categories) from the DevShop catalogue of 1,300+ services. Use when someone asks for free or no-credit-card options, wants a zero-cost stack for a project, or asks "is there a free X".
---

# DevShop: free developer tiers

DevShop (https://jrnoorbaloch.github.io/DevShop/) catalogues 1,300+ services that offer a real free tier, not a short trial. Each record has a name, URL, category, description, free-tier details and tags.

## How to answer

1. **Search the catalogue.** Don't answer from memory, because free tiers change often. Run:

   ```bash
   python3 scripts/find_free_tiers.py "postgres" --limit 10
   python3 scripts/find_free_tiers.py "email api" --tag "No credit card"
   python3 scripts/find_free_tiers.py --category web-hosting --limit 15
   python3 scripts/find_free_tiers.py --list-categories
   python3 scripts/find_free_tiers.py "auth" --json      # machine-readable output
   ```

   Paths are relative to this skill's folder. The script tries the live API first, then falls back to the bundled snapshot in `data/services.json`, so it works offline too.

2. **For a whole project** (for example "free stack for a SaaS MVP"), break it into needs such as hosting, database, auth, email, monitoring, analytics and payments. Run one search per need, then pick 1 to 3 options for each.

3. **Present the results:**
   - Give a short table or list with the service name (linked), what the free tier includes, and any notable tags (*No credit card*, *Open source*, *EU / GDPR*).
   - Link the DevShop page `https://jrnoorbaloch.github.io/DevShop/service/<slug>/` for limits and alternatives.
   - Always add a one-line reminder that free-tier limits change, so the user should confirm on the provider's pricing page.
   - Prefer services whose description states concrete limits, such as "500 MB storage" or "10k requests/month".

## Available tags

`No credit card`, `Open source`, `Unlimited`, `Forever free`, `AI / ML`, `API`, `Students`, `EU / GDPR`, `Self-host option`, `Teams`

## Scope notes

- Self-hosted software is out of scope (DevShop lists only as-a-service offerings).
- Short trials are out of scope. A time-limited tier is listed only if it lasts at least 12 months.
- If nothing matches, say so and suggest broader terms or a nearby category (`--list-categories`).
