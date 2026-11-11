---
name: news-stock-impact
license: MIT
description: Turns today's news into a ranked shortlist of listed companies most exposed to it — naming the event, the transmission mechanism, how much the stock has already moved on it, and what would invalidate the idea. Works on any market (US, UK, India, Japan and others) and any market cap. Use whenever the user asks which stocks or sectors will move on the news, what to buy, watch or trade tomorrow, who benefits from a policy change, rate decision, oil move, earnings surprise or geopolitical event, or mentions today's headlines alongside stocks, shares, tickers, equities, markets or investing — including bare asks like "what's moving tomorrow", "any stock ideas from today's news", or a pasted headline with "how does this affect the market".
---

# News-driven stock impact brief

Produces a shortlist of companies whose earnings are genuinely exposed to today's news, ranked by
how clear the link is and how much of it the market has *not* already absorbed.

The honest premise this rests on: public news is priced fast. By the time a headline is readable,
the obvious trade is usually done — often within minutes. So the value here is not predicting
tomorrow's close. It is doing the work most people skip: tracing a specific event to the specific
line of a specific company's P&L, then checking whether the market has already moved on it.

That reframing is what makes the output usable. A brief that says "Company X, here is the revenue
line that changes, here is how far it already moved today, here is what would prove this wrong" can
be verified and acted on. A list of five tickers with price targets cannot, and it states a
precision this analysis does not have.

## What this needs

Live web access, for news and for price moves. If you cannot search or fetch, **say so and stop** —
do not produce a brief from memory. Recalled prices and market caps are stale by construction, and
a confidently wrong number here costs the user money. Being unable to run is a fine outcome; a
fabricated brief is not.

## Workflow

### 1. Fix the frame before analysing anything

Three things change every downstream answer, so settle them first:

**Which market.** Ask if the user has not said. "Top 5 stocks" means entirely different companies
on the NSE than on the NASDAQ, and the news that matters differs too. Do not default to US markets
because the sources are easiest to find.

**Which session "tomorrow" is.** On a Friday it is Monday. Around a holiday it may be three days
out, and a market that is closed has had no chance to price anything in, which changes the whole
brief. Run:

```bash
python3 scripts/session_clock.py --market IN
python3 scripts/session_clock.py --market US --at 2026-07-31T18:00:00Z
```

It reports whether the market is open now and the date of the next session. Exchange holidays are
not built in — it flags weekends and tells you to verify holidays, which is worth doing when the
next session is more than a day out.

**Which caps are in play.** Any size is allowed, but pick the *leading* names in whichever tier the
news implicates, not the most obscure. Cap tiers are defined differently per market and India has an
official ranked list — see `references/market-conventions.md` for tiers, hours, ticker formats and
the news sources worth reading per market.

### 2. Gather the day's news broadly, before deciding what matters

Search several categories rather than one, because the biggest movers are often not in the business
headlines: central bank and rate decisions, inflation and jobs data, commodities (oil, gas, metals,
agri), currency moves, policy and regulation, tariffs and trade, earnings and guidance, M&A,
company-specific incidents, and geopolitics.

Cast wide first. Narrowing to "tech news" at this stage is how you end up with five semiconductor
names on a day when the actual event was a currency move.

### 3. Keep only what can move a price

Most news cannot. Three filters, applied honestly:

**Is it a surprise?** Markets price expectations, not events. A rate cut everyone forecast moves
nothing; a hold nobody expected moves a lot. Ask what was expected and how the actual differed.
This is the single most common reason a plausible-sounding idea does nothing.

**Does it change cash flows?** A headline that changes sentiment without touching revenue, costs or
risk is noise for this purpose. Name the mechanism — volume, price, input cost, margin, regulatory
cost, financing cost — or drop it.

**Is it fresh?** Check when it broke, not when you read it. A story from three sessions ago has been
traded through. If a "today" story turns out to be a follow-up on last week's news, say so, because
the residual move is much smaller than the headline suggests.

### 4. Trace the mechanism to specific companies

This is the step that separates analysis from keyword matching, and it is where the skill earns its
place.

**Exposure is not association.** "AI news, therefore NVIDIA" is association. Exposure is: this fact
changes this company's revenue or costs, by roughly this much, through this route. If you cannot
name the line that moves, you have not found exposure — you have found a company that operates in
the same general area.

**Concentration decides magnitude.** A pure-play with 70% of revenue in the affected segment moves
far more than a conglomerate with 5%, on identical news. The famous name is frequently the *worse*
pick for exactly this reason. State exposure as a share of revenue or profit wherever you can find
it, and say when you could not.

**Direction is not always obvious.** Most events create losers as well as winners — a jump in crude
lifts producers and squeezes airlines, refiners, paints and logistics. Check both sides; a short
idea or an avoid is often the cleaner read.

**Second-order links are less crowded but weaker.** Everyone buys the obvious name; the component
supplier two steps down the chain may not have moved at all. That is where un-priced exposure
tends to live, and the causal chain is correspondingly more fragile. Use them, and label them as
second-order rather than presenting them with first-order confidence.

`references/impact-mapping.md` has worked transmission chains for the recurring event types — rates,
oil, currency, tariffs, monsoon and weather, defence, regulation — including who is hurt on each.

### 5. Check what is already priced in

The step that most distinguishes a useful brief from a tip sheet. For every candidate, find out
what the stock did **today**:

- How far did it move, and in which direction?
- On what volume relative to normal? Heavy volume means the market read the same news and acted.
- Did it move *before* the headline? That suggests the information was already circulating.

A name up 9% on 5x average volume has largely had its move. That does not always disqualify it —
sustained re-ratings exist — but it must be stated plainly, because it is the difference between
an idea and an idea that has already happened. Where you cannot get an intraday move, say the
check was not possible rather than implying it was clean.

### 6. Rank, then cut to five

Rank on three axes together, not on excitement:

1. **Clarity of mechanism** — can you name the P&L line, or is it a story?
2. **Magnitude of exposure** — what share of the business does it touch?
3. **How much is left** — how much of the move has not happened yet?

Then cut to five. If fewer than five survive honestly, deliver fewer and say why — a padded list
teaches the user to distrust the whole brief. If the day's news genuinely supports none, say that
too. Quiet days exist and are useful information.

## Report structure

Lead with the market and session so the frame is never ambiguous, then one block per name:

```markdown
# News impact brief — <market>, for the <date> session

**Today's dominant story:** <one line — the event actually driving things>
**Breadth:** <sector-wide / a few names / single stock>

## 1. <Company> (<ticker>) — <HIGH / MEDIUM / LOW> exposure

**Event:** <what happened, with source and time>
**Mechanism:** <the specific route to revenue, cost or margin, with the share of the
business affected where known>
**Already moved:** <today's % move and relative volume — or "could not verify">
**Invalidates:** <the concrete fact that would kill this thesis>
**Confidence:** <High / Medium / Low, and why>

## ... (repeat, ranked)

## Losers / avoid
<names hurt by the same news, where relevant>

## What I could not verify
<gaps — unavailable prices, unconfirmed revenue splits, sources behind paywalls>
```

The **Invalidates** line is not decoration. Writing down what would prove the idea wrong is what
turns a tip into a thesis, and it gives the user something concrete to watch tomorrow.

## Failure modes worth naming

**Picking the household name over the exposed one.** The most-covered company in a sector is rarely
the most exposed to a specific event. Check revenue concentration before defaulting to the giant.

**Treating sector news as company news.** "Banks rallied" says nothing about which bank has the
loan book that actually benefits. Push through to the company.

**Reading a follow-up as a fresh catalyst.** Second-day coverage of an event is the same event.
Date every story.

**Small caps without a liquidity check.** A small cap with direct exposure gives the biggest move
and the worst exit. Where you pick one, note its typical traded volume, and in markets with daily
price bands or circuit limits (India especially) note that a limit-up move cannot be bought into.

**Silent staleness.** Market caps, revenue splits and prices recalled rather than looked up are the
main source of confident errors here. Verify, or mark unverified.

## Judgement calls

**Say when the day is thin.** Some sessions have no tradeable news. Reporting that honestly is more
valuable than manufacturing five ideas from a quiet Tuesday.

**Separate what happened from what you infer.** The event is fact; the earnings impact is your
estimate. Keep them visibly distinct so the user can disagree with the inference while trusting the
reporting.

**Prefer the boring mechanism.** Currency, input costs and regulation move earnings more reliably
than narrative shifts, and they are far easier to verify.

**Report confidence honestly, including low.** A LOW-confidence idea labelled as such is useful. The
same idea labelled HIGH is misinformation.

## What this is not

This produces research for the user to verify, not investment advice, and it cannot know their
finances, tax position, time horizon or risk tolerance. Say so once, plainly, at the end of the
brief — and make it true by showing the reasoning and sources so the conclusions can be checked
rather than taken on trust.

Do not state entry prices, targets or stop-losses. That framing implies a precision that
news-to-earnings analysis does not have, and it converts a research shortlist into a tip sheet the
user cannot evaluate.
