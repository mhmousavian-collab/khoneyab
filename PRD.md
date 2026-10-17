# PRD: خونه‌یاب — Intent-Aware Home Search

## 1. Product goal

Build a working, Torob-inspired residential-property search product for Iran. Users should be able to search properties for sale or rent across multiple Iranian cities, refine results with filters or natural language, understand why properties rank highly, and compare their trade-offs.

The recruitment demo prioritizes **end-to-end full-stack execution**: a polished, usable interface connected to a real API and persistent database. Use synthetic data only; never imply that demo listings or prices are live.

## 2. Target users

Anyone looking to buy or rent a residential property in Iran, including people who know exactly what they want and people who need help exploring trade-offs.

## 3. MVP scope

### Must have

- Persian-first, right-to-left, responsive web UI.
- Search for both **sale** and **rent** across multiple Iranian cities from launch.
- Conventional filters and natural-language search.
- Search results ranked by intent, with concise reasons showing matches and trade-offs.
- Property-detail pages.
- List/map view toggle.
- Compare up to three properties side by side.
- Favorite properties and save searches in browser local storage; no account required.
- Group likely duplicate advertisements so one property does not dominate results.
- A synthetic, seeded dataset stored in a persistent database.
- Optional AI features through configurable OpenAI-compatible endpoints; core product must work without an API key or an LLM endpoint.
- Run the whole application with Docker Compose.

### Not in scope

Live scraping/crawling, real listing feeds, user accounts, contacting agents, payments, production-grade geocoding, or claims about real-time market prices. Do not add unrelated features or complex agent orchestration.

## 4. Core user flow

1. On the home/search page, the user chooses sale or rent, selects a city if desired, and enters a query in Persian. Show a few example queries.
2. The app interprets the query into editable criteria. Show these as chips or filter controls, separating **must-haves** from **preferences**.
3. The results page shows ranked property cards with price, location, key specifications, a match score, and short evidence-based reasons. Users can change filters, sort, or switch between list and map.
4. The user can open a property, inspect its details and approximate location, favorite it, save the search, or add it to a comparison of up to three properties.
5. The comparison view highlights meaningful differences and trade-offs, not just a repeated list of fields.

## 5. Search, filtering, and ranking

- Basic filters must be deterministic and must not make LLM calls: transaction, city, neighborhood, property type, budget, area, bedrooms, amenities, and transit distance.
- Support natural-language queries such as: «آپارتمان دو خوابه برای خرید در تهران تا ۱۵ میلیارد تومان، نزدیک مترو و دارای پارکینگ».
- Normalize Persian and Arabic digits, common spelling variants, separators, area units, and toman/rial inputs.
- Treat explicit limits and phrases such as “must have” as hard constraints. Treat ordinary preferences such as “near the metro” as soft preferences unless the user makes them mandatory.
- Filter on hard constraints first. Rank remaining properties using a deterministic, transparent weighted score based on soft-preference matches. Explicitly emphasized preferences receive higher weight. The exact weights should be centralized and easy to tune.
- Show a simple match score and evidence-based reasons, for example: “within budget”, “parking available”, and “about 7 minutes from transit”. Also identify important unmet preferences. Do not invent facts that are absent from the listing data.
- If no properties satisfy the hard constraints, keep the strict results empty and offer a clearly separated **near matches** section that states which constraint each suggestion fails. Never silently relax the user’s hard constraints.
- Provide filters and sorting that work without AI. At minimum, sort by relevance, price, and area.
- Group likely duplicate ads conservatively using normalized fields such as city, neighborhood, area, bedrooms, floor, and description similarity. Display one result per likely property group, show the number of grouped ads, and allow users to inspect group/source details. Avoid merging properties when evidence is weak.

## 6. Data requirements

Seed the backend database with at least **150 synthetic advertisements** spanning at least **8 Iranian cities**, multiple neighborhoods per city, both sale and rent, different property types, price bands, amenities, and transit distances. Include several deliberately messy duplicate groups and enough exact and near-match cases to demonstrate ranking and trade-offs. Seed data must be repeatable and must not be reset on every restart.

Every normalized property/ad record should support:

- Transaction type: sale or rent.
- Property type: apartment, house, or villa.
- City and neighborhood.
- Approximate latitude/longitude for map display.
- Area in square meters and bedroom count.
- Sale price, or rental deposit and monthly rent, in toman.
- Price per square meter for sale properties, calculated from price and area.
- Floor number and total building floors, where applicable.
- Building age in years.
- Amenities: at least parking, elevator, and storage.
- Nearby public transport: mode/station name, approximate distance and/or walking minutes.
- Short neighborhood information.
- Description, image references, listing/post date, and source name.
- Optional original-source URL, nullable because demo data is synthetic.
- Duplicate-group identifier or equivalent grouping relationship.

Use local bundled demo images or consistent local placeholders. Mark the application and listings as demo/synthetic. Do not fabricate working links to real advertisements. Approximate coordinates and transit distances must be presented as approximate.

## 7. AI integration

Create one backend-only AI provider abstraction for OpenAI-compatible chat-completions endpoints. Configure three independent tiers with environment variables for base URL, model name, and optional API key:

- `AI_CHEAP_BASE_URL`, `AI_CHEAP_MODEL`, `AI_CHEAP_API_KEY`
- `AI_STANDARD_BASE_URL`, `AI_STANDARD_MODEL`, `AI_STANDARD_API_KEY`
- `AI_PREMIUM_BASE_URL`, `AI_PREMIUM_MODEL`, `AI_PREMIUM_API_KEY`

No API key is required for local endpoints that do not use one. Never expose credentials to the browser or log their values.

Default task routing:

- Cheap tier: interpret natural-language searches into structured criteria.
- Standard tier: help refine a search across follow-up messages.
- Premium tier: optional natural-language synthesis of a multi-property comparison, only when requested.

Search filters, ranking, match scores, and factual match/trade-off evidence must be computed by application code, not delegated to the LLM. Validate model output against a schema before using it. If AI is unavailable or unconfigured, use a basic rule-based Persian query parser for common patterns and template-based explanations. All core user flows must remain usable without AI.

## 8. UI direction

- Torob-inspired information hierarchy: prominent search, compact results, strong emphasis on finding and comparing the best match. Do not copy Torob branding or claim affiliation.
- Clean light theme, neutral backgrounds, restrained green accent, clear typography, compact property cards, and consistent spacing.
- Persian-first RTL layout; format numbers and prices naturally for Persian users and label the currency as تومان.
- The results page should make it easy to see price, location, area, bedrooms, key amenities, transit proximity, match reasons, and comparison/favorite actions at a glance.
- Map pins represent approximate locations. The map must have a usable list fallback if map tiles cannot load.
- Include loading, empty, error, and AI-unavailable states; do not leave controls as visual-only mockups.

## 9. Suggested implementation

- Frontend: React + TypeScript + Vite.
- Backend: Python + FastAPI, with request/response schemas and a clear separation between API, search/ranking, deduplication, and AI-provider logic.
- Database: SQLite with a Docker volume for persistence; use migrations or a simple versioned schema setup.
- Map: Leaflet with OpenStreetMap tiles, without requiring a paid map API key.
- Favorites and saved searches: browser `localStorage`; no authentication.
- Docker Compose: one command builds and starts frontend and backend. The backend seeds the database only when it is empty. Keep AI configuration in environment variables and provide an `.env.example` with empty optional credentials.

## 10. Acceptance criteria

1. `docker compose up --build` starts the complete app, and the UI can reach the backend API.
2. Reloading/restarting does not erase the seeded database, favorites, or saved searches.
3. Sale and rent searches work across multiple Iranian cities; filters and sorting operate without AI.
4. A Persian natural-language query produces editable structured criteria, using an available cheap model or the rule-based fallback.
5. Results obey hard constraints, rank soft preferences, and show accurate reasons and unmet preferences derived from stored data.
6. Empty exact matches produce separately labelled near matches without hiding which constraint was relaxed.
7. Duplicate advertisements are grouped into one result when evidence is strong, with the grouped-ad count visible.
8. Users can switch list/map views, open a detail page, favorite a property, save a search, and compare up to three properties.
9. The comparison view highlights actual differences in price, area, location, amenities, and transit proximity.
10. With all AI variables unset and no API key, the full core flow still works and no AI-related error blocks the experience.
11. Include basic automated tests for filtering, ranking, query parsing fallback, duplicate grouping, and API health/search endpoints.

## 11. Demo scenario

Demonstrate an apartment-for-sale query in Tehran with a two-bedroom requirement, a maximum budget, parking, and proximity to the metro. Show the interpreted criteria, ranked results and evidence-based trade-offs; switch to the map; compare three properties; open one detail page; then save the search and favorite a property. Keep the entire walkthrough suitable for a five-minute demo.
