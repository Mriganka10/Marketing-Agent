# End-to-End Test Cases

Use this guide to manually validate and demo the full Marketing Agent flow in production.

Production URL:

```text
https://agenticgrowthlabs.com
```

## Demo Objective

The end-to-end business story is:

```text
Understand a company -> find demand -> generate SEO pages -> capture leads -> track Google and GA4 performance -> recommend page refreshes
```

The client-facing value is:

- reduce manual SEO research and page creation work,
- publish targeted campaign pages faster,
- capture and score inbound leads,
- measure which pages are visible in Google,
- understand which pages convert,
- recommend what to improve next.

## Suggested Demo Business Values

Use realistic values so the demo feels business-ready.

### Option A: Kairoz Corporation

```text
Business name: Kairoz Corporation
Website: https://kairozcorporation.com
Industry: B2B marketing automation and AI operations
Tone: confident, practical, enterprise-ready
Audience: SaaS founders, growth leaders, and revenue operations teams
Value proposition: Kairoz helps B2B companies launch AI-assisted marketing operations that identify demand, publish targeted landing pages, capture qualified leads, and improve campaigns using analytics.
Offers: AI marketing automation, SEO landing pages, lead capture automation, campaign analytics
Competitors: Clay, Copy.ai, Jasper, HubSpot
```

Campaign:

```text
Campaign name: AI marketing growth pages for SaaS
Target region: India
Goal: Generate qualified demo requests from SaaS and technology companies looking for scalable AI-assisted marketing operations.
```

### Option B: GreyRadius

```text
Business name: GreyRadius
Website: https://www.highradius.com
Industry: enterprise finance automation
Tone: authoritative, analytical, CFO-focused
Audience: CFOs, controllers, credit teams, and accounts receivable leaders
Value proposition: GreyRadius helps finance teams automate receivables, improve cash flow visibility, reduce manual collections effort, and accelerate working capital outcomes.
Offers: accounts receivable automation, collections automation, cash application, credit risk analytics
Competitors: HighRadius, Billtrust, BlackLine, Tesorio
```

Campaign:

```text
Campaign name: Finance automation demand pages
Target region: United States
Goal: Generate qualified finance transformation leads from companies searching for accounts receivable and collections automation.
```

## Test Case 1: Save A Business

Business value:

Creates the business memory that all other agents use. This replaces repeated manual briefing across SEO, copywriting, analytics, and campaign teams.

Goal:

Create a business profile that all later agents can use.

Steps:

1. Open `https://agenticgrowthlabs.com/#launch`.
2. In `Business profile`, enter one of the suggested demo businesses above or a real client business.
3. Click `Save business`.
4. Wait for the processing overlay to finish.

Expected result:

- A success toast appears.
- The business appears in the campaign business dropdown.
- `Activity -> Governance` shows a `business_profile_created` audit event.

Evidence to show the client:

- The saved business profile.
- The audit event proving the business memory was stored.

Business interpretation:

The system now understands the company's market, offer, audience, competitors, and tone. This becomes reusable context for research, content generation, and refresh recommendations.

## Test Case 2: Launch The Agent Loop

Business value:

Runs the core growth workflow from one action instead of manually coordinating research, copywriting, page publishing, and analytics setup.

Goal:

Run Research, Content/Page Creation, and Analytics/Refresh agents.

Steps:

1. Stay on `https://agenticgrowthlabs.com/#launch`.
2. Select the saved business from the `Business` dropdown.
3. Enter campaign name, target region, and campaign goal.
4. Keep `Publish generated pages` checked.
5. Click `Launch agent loop`.
6. Wait for processing to finish.

Expected result:

- New demand signals are generated.
- New pages are created and published.
- Recommendations are generated.
- `Pages` count increases on Overview.

Evidence to show the client:

- Newly created page count.
- Generated demand signals or campaign output.
- Activity/audit events for the run.

Business interpretation:

The agents converted a business brief into campaign assets and measurable landing pages.

## Test Case 3: Open A Generated Content Page

Business value:

Confirms that AI-generated campaign content is not just draft copy. It becomes a public, trackable landing page that can capture traffic and leads.

Goal:

Confirm the generated page is public and trackable.

Steps:

1. Go to `https://agenticgrowthlabs.com/#pages`.
2. Click `Open` on a generated page.
3. Confirm the public URL opens:

```text
https://agenticgrowthlabs.com/p/{slug}
```

Expected result:

- Page loads with title, hero copy, sections, and lead form.
- Page contains GA4 browser tracking.
- Page is included in `https://agenticgrowthlabs.com/sitemap.xml`.

Evidence to show the client:

- The live URL.
- The page headline and CTA.
- The lead form.

Business interpretation:

The page is ready to be shared, crawled, tracked, and measured.

## Test Case 4: Submit A Test Lead

Business value:

Shows that the generated page can convert anonymous visitors into trackable business leads.

Goal:

Confirm lead capture and conversion flow.

Steps:

1. Open a generated public page.
2. Fill the lead form with a realistic test lead.
3. Submit the form.
4. Return to `https://agenticgrowthlabs.com/#activity`.

Suggested test lead:

```text
Name: Demo Buyer
Email: demo.buyer@example.com
Company: Demo Enterprise
Message: We are evaluating AI-assisted marketing pages and lead capture for our growth team.
```

Expected result:

- New lead appears in `Activity -> Leads`.
- Lead has score and status.
- Dashboard lead count increases.

Evidence to show the client:

- Lead row in Activity.
- Lead score and status.
- Source page if visible.

Business interpretation:

The system closes the loop from page creation to lead capture, so SEO output can be tied to pipeline activity.

## Test Case 5: Confirm GA4 Realtime Tracking

Business value:

Proves that page visits are being sent to Google Analytics so campaign performance can be measured beyond internal app counters.

Goal:

Confirm GA4 receives browser page events.

Steps:

1. Open GA4 property `544328945`.
2. Go to `Reports -> Realtime`.
3. Open a generated public page in another browser tab.
4. Wait 10-60 seconds.

Expected result:

- Realtime should show an active user.
- Page path should eventually include:

```text
/p/{slug}
```

Evidence to show the client:

- GA4 Realtime active user.
- Page path for the generated landing page.

Notes:

- Realtime appears quickly.
- Standard GA4 reports may take several hours.
- GA4 sessions can differ from Google Search clicks because they measure different things.

Business interpretation:

The campaign page is measurable in GA4 and can be connected to traffic source, engagement, and conversion analysis.

## Test Case 6: Submit Sitemap In Search Console

Business value:

Helps Google discover generated pages faster by submitting the site map of published URLs.

Goal:

Help Google discover generated pages.

Steps:

1. Open Google Search Console for `agenticgrowthlabs.com`.
2. Go to `Sitemaps`.
3. Submit:

```text
sitemap.xml
```

Expected result:

- Sitemap submission is accepted.
- Google starts processing discovered URLs.

Evidence to show the client:

- Submitted sitemap status in Search Console.
- Discovered URL count after Google processes it.

Business interpretation:

This makes the generated page inventory discoverable to Google, which is required before search impressions and clicks can happen.

## Test Case 7: Inspect A Generated URL In Search Console

Business value:

Shows whether Google can see and evaluate an individual campaign page.

Goal:

Check whether Google can index the generated page.

Steps:

1. Copy a generated page URL:

```text
https://agenticgrowthlabs.com/p/{slug}
```

2. Paste it into Search Console `URL inspection`.
3. Press Enter.
4. If available, click `Request indexing`.

Expected result:

- Search Console reports whether the URL is known to Google.
- If not indexed yet, request indexing starts Google discovery.

Evidence to show the client:

- URL inspection result.
- Indexing request status if submitted.

Notes:

- New pages usually do not appear in Google immediately.
- Indexing can take hours to days.
- Google may index a page but rank it low at first.

Business interpretation:

The agent helps create index-ready pages, while Search Console confirms whether Google has discovered and indexed them.

## Test Case 8: Search In Google

Business value:

Validates whether a generated page is visible in public Google results.

Goal:

Check whether Google has indexed the generated page.

Steps:

1. Search Google using:

```text
site:agenticgrowthlabs.com/p/{slug}
```

2. Try a keyword from the generated page title.

Expected result:

- If indexed, the page appears in results.
- If not indexed, wait and recheck Search Console.

Evidence to show the client:

- Search result screenshot if the page appears.
- Search Console indexing status if it does not appear.

Business interpretation:

Google visibility is not guaranteed immediately. The system supports discovery and improvement, but ranking depends on Google crawl/index/rank decisions.

## Test Case 9: Sync SEO Metrics

Business value:

Pulls external Google data back into the Marketing Agent so the client can see page performance in one operating dashboard.

Goal:

Pull Search Console and GA4 data into Marketing Agent.

Steps:

1. Open `https://agenticgrowthlabs.com/#seo`.
2. Click `Sync SEO metrics`.
3. Wait for processing to finish.

Expected result:

- SEO mode shows `live google integrated`.
- Page performance cards refresh.
- If Google has data, cards show:

```text
Google impressions
Google clicks
CTR
Average position
GA4 sessions
Leads
Conversion rate
Recommendation
```

If Google has no processed data yet:

- Search metrics show zero.
- GA4 sessions show zero.
- Recommendation usually indicates low search discovery.

Evidence to show the client:

- `live google integrated` status.
- Page performance cards.
- Sync timestamp if visible through API/integration status.

Business interpretation:

The system joins Google visibility, website visits, and captured leads into a page-level refresh plan.

## Test Case 10: Filter By Company

Business value:

Lets each client or business unit view only its own campaign pages and metrics.

Goal:

Show a client only its own page stats.

Steps:

1. Open `https://agenticgrowthlabs.com/#seo`.
2. In `Page performance and refresh plan`, use the `Company` dropdown.
3. Select a company, for example:
   - Kairoz Corporation
   - GreyRadius
   - Contify
4. Review the filtered page cards.

Expected result:

- Only pages belonging to the selected company are shown.
- `need refresh` count updates for that filtered company.

Evidence to show the client:

- Company dropdown selection.
- Filtered page list.
- Company name on each page card.

Business interpretation:

This supports multi-company or agency-style demos where each organization needs a separate performance view.

## Test Case 11: Interpret The SEO Recommendation

Business value:

Turns raw SEO metrics into the next best action for growth.

Example card:

```text
Page: /p/ai-marketing-for-saas
Google impressions: 1,240
Google clicks: 86
CTR: 6.9%
Average position: 14.2
GA4 sessions: 92
Leads: 7
Conversion rate: 7.6%
Recommendation: Create variants by keyword, geography, persona, or industry to scale the winning pattern.
```

Decision logic:

- Low impressions: improve keyword targeting, sitemap coverage, links, and content depth.
- High impressions but low CTR: rewrite title and meta description.
- Traffic but low conversion: improve hero, CTA, proof, offer, and form friction.
- Good conversion: create similar pages for more keywords, regions, or personas.

Evidence to show the client:

- Recommendation text on the page card.
- Metrics that explain why the recommendation was made.

Business interpretation:

The agent reduces manual analysis by explaining whether the page needs discovery work, click-through improvement, conversion improvement, or campaign expansion.

## Test Case 12: Explain Key Metrics To A Client

Business value:

Ensures stakeholders understand what the dashboard is measuring and how to act on it.

Goal:

Explain the difference between traffic, impressions, clicks, visits, leads, and conversion.

Metric definitions:

```text
Traffic: Overall flow of users from all channels.
Impressions: How many times Google showed the page in search results.
Clicks: How many users clicked the page from Google Search.
CTR: Clicks divided by impressions.
Average position: Average Google ranking position.
Visits / sessions: GA4 visits to the page from all tracked channels.
Leads: Submitted forms or business-intent actions.
Conversion rate: Leads divided by sessions.
Indexing: Google has stored the page so it can appear in search.
Ranking: Where the page appears for a query.
```

Expected result:

- Client understands that impressions and clicks come from Search Console.
- Client understands that sessions come from GA4.
- Client understands that leads come from the Marketing Agent lead capture flow.

Business interpretation:

The dashboard connects search visibility, user behavior, and lead outcomes into one measurable growth loop.

## Test Case 13: Confirm Backend Health

Business value:

Confirms that production services are available and Google integrations are configured.

Commands:

```bash
curl https://agenticgrowthlabs.com/health
curl https://agenticgrowthlabs.com/api/seo/integrations
curl https://agenticgrowthlabs.com/api/seo/overview
```

Expected result:

```text
status: ok
mode: live_google_integrated
ga4: live_synced
google_search_console: live_synced
```

Evidence to show internally:

- Health endpoint returns `ok`.
- Integration endpoint shows GA4 and Search Console configured.
- SEO overview endpoint returns page scores.

Business interpretation:

The app, SEO dashboard, and Google integration layer are healthy enough for demo or operational testing.

## Test Case 14: Run Growth Suite Agents

Business value:

Shows the client that the product is no longer only a landing-page generator. It is a broader growth operating system covering AI visibility, authority, paid campaigns, reporting, and workspace governance.

Steps:

1. Open `https://agenticgrowthlabs.com`.
2. Go to `Growth Suite`.
3. Review the integration readiness board.
4. Click `Run growth suite`.
5. Wait for the processing overlay to complete.
6. Confirm six agent cards are visible:
   - AI Search Visibility Agent
   - Backlink / Authority Agent
   - Auto Refresh + Approval Agent
   - Paid Campaign Agent
   - Client Reporting Agent
   - Client Workspace / Access Control Agent
7. Review client workspaces and the executive report snapshot.
8. Go to `Activity` and confirm a `growth_suite_synced` audit event exists.

Expected result:

- The Growth Suite page stays aligned on desktop and mobile.
- Each agent card shows status, mode, metrics, and recommendations.
- Missing DataForSEO or Google Ads credentials show as pending rather than breaking the demo.
- Client workspace cards are grouped by company/business.

Business interpretation:

The suite demonstrates a full agency replacement workflow: visibility analysis, authority planning, page refresh planning, paid campaign readiness, client reporting, and controlled client-specific workspaces.

## Test Case 15: Validate Third-Party Credential Readiness

Business value:

Confirms which parts are live and which parts are waiting on external approval or credentials before promising client outcomes.

Steps:

1. Open `Growth Suite`.
2. Check the readiness board.
3. Confirm OpenAI shows ready when `OPENAI_API_KEY` is configured.
4. Confirm DataForSEO shows ready after `DATAFORSEO_ENABLED`, login, and password are added.
5. Confirm Google Ads shows ready after developer token, OAuth client, refresh token, and customer IDs are added.
6. Confirm Google Ads may still return pending/fallback while Google Basic Access review is pending.

Expected result:

```text
OpenAI visibility: Ready
DataForSEO authority: Ready after API credentials and account balance
Google Ads API: Ready after credentials, but campaign reads may wait for Google access approval
GA4 + Search Console: Ready after service account access and sync
```

Business interpretation:

This prevents over-claiming. The platform can demo the complete workflow immediately, while live external data depends on the third-party access status.

## End-To-End Acceptance Criteria

The full test is successful when:

- a business profile is saved,
- an agent loop completes,
- generated pages are public under `https://agenticgrowthlabs.com/p/...`,
- a lead can be submitted from a generated page,
- lead appears in Activity,
- GA4 Realtime can detect page activity,
- sitemap is available and submitted,
- Search Console can inspect the page,
- SEO dashboard syncs in `live_google_integrated` mode,
- company filter narrows page performance cards,
- Growth Suite runs all six additional agents,
- readiness cards clearly show OpenAI, DataForSEO, Google Ads, GA4, and Search Console status,
- client workspaces separate metrics by business,
- recommendations explain what to improve next.

## Known Timing Expectations

Use these expectations when explaining delays:

```text
Generated page opens: immediate
Lead capture: immediate
GA4 Realtime: usually 10-60 seconds
GA4 standard reports: several hours
Search Console discovery: hours to days
Google indexing: hours to days or longer
Google ranking movement: days to weeks
Organic traffic growth: depends on search demand, competition, page quality, and domain authority
```
