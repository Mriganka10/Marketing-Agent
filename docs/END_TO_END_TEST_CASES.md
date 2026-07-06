# End-to-End Test Cases

Use this guide to manually validate the full Marketing Agent flow in production.

Production URL:

```text
https://agenticgrowthlabs.com
```

## Test Case 1: Save A Business

Goal:

Create a business profile that all later agents can use.

Steps:

1. Open `https://agenticgrowthlabs.com/#launch`.
2. In `Business profile`, enter:
   - Business name
   - Website
   - Industry
   - Tone
   - Audience
   - Value proposition
   - Offers
   - Competitors
3. Click `Save business`.
4. Wait for the processing overlay to finish.

Expected result:

- A success toast appears.
- The business appears in the campaign business dropdown.
- `Activity -> Governance` shows a `business_profile_created` audit event.

## Test Case 2: Launch The Agent Loop

Goal:

Run Research, Content/Page Creation, and Analytics/Refresh agents.

Steps:

1. Stay on `https://agenticgrowthlabs.com/#launch`.
2. Select the saved business from the `Business` dropdown.
3. Enter campaign name, region, and goal.
4. Keep `Publish generated pages` checked.
5. Click `Launch agent loop`.
6. Wait for processing to finish.

Expected result:

- New demand signals are generated.
- New pages are created and published.
- Recommendations are generated.
- `Pages` count increases on Overview.

## Test Case 3: Open A Generated Content Page

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
- Page contains GA4 tracking.
- Page is included in `https://agenticgrowthlabs.com/sitemap.xml`.

## Test Case 4: Submit A Test Lead

Goal:

Confirm lead capture and conversion flow.

Steps:

1. Open a generated public page.
2. Fill the lead form.
3. Submit the form.
4. Return to `https://agenticgrowthlabs.com/#activity`.

Expected result:

- New lead appears in `Activity -> Leads`.
- Lead has score and status.
- Dashboard lead count increases.

## Test Case 5: Confirm GA4 Realtime Tracking

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

Notes:

- Realtime appears quickly.
- Standard GA4 reports may take several hours.

## Test Case 6: Submit Sitemap In Search Console

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

## Test Case 7: Inspect A Generated URL In Search Console

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

Notes:

- New pages usually do not appear in Google immediately.
- Indexing can take hours to days.

## Test Case 8: Search In Google

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

## Test Case 9: Sync SEO Metrics

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

## Test Case 10: Filter By Company

Goal:

Show a client only its own page stats.

Steps:

1. Open `https://agenticgrowthlabs.com/#seo`.
2. In `Page performance and refresh plan`, use the `Company` dropdown.
3. Select a company, for example:
   - Kairoz Corporation
   - GreyRadius
4. Review the filtered page cards.

Expected result:

- Only pages belonging to the selected company are shown.
- `need refresh` count updates for that filtered company.

## Test Case 11: Interpret The SEO Recommendation

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

## Test Case 12: Confirm Backend Health

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
