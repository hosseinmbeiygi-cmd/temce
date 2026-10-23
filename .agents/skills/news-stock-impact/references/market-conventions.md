# Market conventions

Per-market facts that change how a brief is written: what counts as large/mid/small cap, how
tickers are written, which sources carry the news that moves prices, and the local quirks that
trip up an analysis done with US assumptions.

Read the section for the market in play. Session times live in `scripts/session_clock.py` — run it
rather than reasoning about timezones in prose.

## Contents

- [United States](#united-states)
- [India](#india)
- [United Kingdom](#united-kingdom)
- [Japan](#japan)
- [Markets not listed here](#markets-not-listed-here)
- [Cross-market cautions](#cross-market-cautions)

---

## United States

**Exchanges:** NYSE, NASDAQ. **Indices:** S&P 500, NASDAQ 100, Russell 2000 (small cap), Dow 30.

**Cap tiers** are convention, not regulation — no official list exists, so state the market cap you
used rather than just the label:

| Tier | Rough range |
| --- | --- |
| Mega | above $200B |
| Large | $10B – $200B |
| Mid | $2B – $10B |
| Small | $300M – $2B |
| Micro | below $300M |

**Tickers:** plain symbols (`AAPL`, `NVDA`). Class shares use a suffix that differs by vendor
(`BRK.B` vs `BRK-B`) — write the plain form and note the class.

**Sources:** company 8-K and 10-Q filings on SEC EDGAR are the primary record and are free; Reuters,
Bloomberg, CNBC, WSJ for the narrative. Fed statements and the FOMC calendar for rates; BLS for
jobs and CPI.

**Quirks:** pre-market (from 04:00 ET) and after-hours (to 20:00 ET) is where earnings reactions
first appear, so a stock can have "already moved" before the regular session opens — check extended
hours before concluding the move has not happened. Earnings are typically released just before the
open or just after the close, rarely mid-session.

---

## India

**Exchanges:** NSE (dominant for volume), BSE. **Indices:** NIFTY 50, SENSEX, NIFTY Midcap 150,
NIFTY Smallcap 250.

**Cap tiers are officially defined here**, which is unusual and useful — SEBI mandates the
classification and AMFI publishes the ranked list twice a year (June and December), based on full
market capitalisation averaged across exchanges where a stock is dual-listed:

| Tier | Definition |
| --- | --- |
| Large cap | Rank 1–100 by full market cap |
| Mid cap | Rank 101–250 |
| Small cap | Rank 251 onwards |

When the user asks for "top companies of that cap", this ranked list is the objective answer for
India — cite the rank rather than asserting a tier.

**Tickers:** NSE uses alphabetic symbols (`RELIANCE`, `TCS`, `HDFCBANK`); BSE uses six-digit numeric
codes (`500325`). Data vendors suffix them `.NS` and `.BO`. Give the NSE symbol by default.

**Sources:** exchange filings on nseindia.com and bseindia.com are primary and free. Economic
Times, Business Standard, Mint, Moneycontrol for coverage. RBI for rates and policy; SEBI for
regulation; PIB for government announcements.

**Quirks that matter:**

- **Daily price bands (circuit limits).** Many mid and small caps have 5%, 10% or 20% daily bands.
  A stock locked limit-up cannot be bought — there are no sellers. Always check the band before
  recommending a small cap on fresh news, because "up 20%" may mean "untradeable".
- **Promoter holding and pledges** are disclosed and material. A pledged-promoter stock reacts
  differently to bad news.
- **ASM/GSM surveillance lists** impose extra margins on volatile small caps, which suppresses
  participation.
- The market is heavily influenced by crude (India imports the large majority of its oil) and by
  the monsoon, which drives rural demand. Both are recurring news categories with wide read-across.

---

## United Kingdom

**Exchange:** London Stock Exchange. **Indices:** FTSE 100 (large), FTSE 250 (mid), FTSE SmallCap,
AIM (growth/small, lighter regulation).

**Cap tiers** track index membership in practice — FTSE 100 for large, FTSE 250 for mid, AIM for
the speculative tail. Say which index a name sits in; it is more informative to a UK reader than an
absolute market cap.

**Tickers:** TIDM codes (`BP`, `HSBA`, `SHEL`), suffixed `.L` by data vendors.

**Sources:** RNS (Regulatory News Service) announcements are the primary record for anything
price-sensitive and are the UK equivalent of an 8-K. Financial Times, Reuters, The Times for
coverage. Bank of England for rates; ONS for inflation and GDP.

**Quirks:**

- **Prices are quoted in pence, not pounds.** A "2,450" quote is £24.50. Getting this wrong by 100x
  is the single most common error in UK analysis — state the unit explicitly.
- The FTSE 100 earns most of its revenue abroad, so a weaker pound tends to *lift* the index while
  hurting domestically focused FTSE 250 names. Index direction and domestic economic news often
  point opposite ways, which is counterintuitive if you carry US assumptions over.

---

## Japan

**Exchange:** Tokyo Stock Exchange. **Segments** since the 2022 restructure: Prime (largest,
strictest governance), Standard, Growth. **Indices:** Nikkei 225 (price-weighted, so high-priced
shares dominate moves), TOPIX (cap-weighted, broader).

**Cap tiers:** use the TSE segment plus market cap. Prime membership is the closest thing to a
large-cap marker.

**Tickers:** four-digit numeric codes (`7203` Toyota, `6758` Sony), suffixed `.T` by vendors. Give
the code and the name together — the codes are not guessable.

**Sources:** TDnet for company disclosures, Nikkei for coverage, Bank of Japan for policy.

**Quirks:**

- **Two sessions with a midday break** (see the session clock). News breaking during the break has
  a pending reaction rather than an absorbed one.
- The Nikkei being price-weighted means a single high-priced stock can move the index without the
  market broadly moving — do not read index moves as breadth.
- The yen is a dominant driver: a weaker yen lifts exporters (autos, machinery, electronics) and
  squeezes importers and domestic retail. Currency news is frequently the real story behind an
  equity move.

---

## Markets not listed here

Do not assume US hours, US cap conventions or US disclosure norms. Look up, and state in the brief:

1. Trading hours and timezone, including any midday break.
2. Whether an official cap classification exists, or whether you are using an index proxy.
3. The primary disclosure channel — most markets have a mandatory filing service equivalent to
   EDGAR or RNS, and it is more reliable than press coverage.
4. Whether daily price limits apply.
5. Currency, and whether foreign investors face access restrictions that make a name effectively
   untradeable for the user.

---

## Cross-market cautions

**Dual listings and ADRs/GDRs move separately.** The local line and the ADR can diverge on
currency and on time-zone lag. Say which line you mean.

**Match the news geography to the revenue geography.** A European tariff story hits an Indian
exporter only in proportion to its European revenue. This is the most frequent source of
mechanically wrong picks — the company is in the right industry but the wrong market.

**A closed market has priced in nothing.** When news breaks while the target market is shut, the
reaction is still ahead. That is genuinely useful, and it is the one case where a brief can point
at something that has not already happened — check whether ADRs, futures or a related market
traded in the meantime, because those give the best available read on where it opens.
