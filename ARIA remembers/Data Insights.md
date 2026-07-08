---
title: Data Insights
type: research
tags: [data, analysis, leads, research]
updated: 2026-05-07
---

# Data Insights

← [[HOME]] | Full report: `Architecture/ARIA_Lead_Analysis.docx`

## Source data

Two Excel files analysed:
- `Sample Leads.xlsx` — lead records (name, type, date created, etc.)
- `Follow Up.xlsx` — what was done with each lead (follow-up 1 date, outcome)

## The headline finding

> **202 days** average gap between lead creation date and first follow-up attempt.

This is the core business case for ARIA. A 202-day gap means most leads are stone cold by the time anyone reaches out.

## Key stats

| Metric | Value |
|--------|-------|
| Avg. first response gap | 202 days |
| Connection rate | 7% |
| Leads with no follow-up | Majority |
| Most common outcome | No response / not reached |

## Lead type distribution

The dataset showed a mix of agents, brokers, and POSP advisors. Brokers had better response rates — consistent with their higher scoring in [[Lead Scoring]].

## Response gap distribution

- A small fraction of leads were contacted within days (likely hot inbound leads)
- The bulk clustered at 100–300 days
- Long tail extended past 365 days

## What this means for ARIA

1. **Speed beats perfection** — even a mediocre message sent in 4 minutes beats a perfect message sent in 202 days
2. **Follow-up scheduling is critical** — leads that don't reply need a 24hr and 72hr nudge (see [[Message Templates]])
3. **Lead quality scoring matters** — with 7% connection rate, prioritising hot leads conserves human time
4. **The KB gap is real** — many follow-up failures were due to not having answers to common questions. 21 KB placeholders need filling.

## Charts in the report

| Chart | Key insight |
|-------|------------|
| First call outcome distribution | Most outcomes were negative — didn't pick up, number invalid |
| Response gap histogram | Confirmed the 202-day average |
| Pipeline funnel | Drop-off at every stage |
| Lead type breakdown | Agent and broker dominate the dataset |

## Data gaps we noticed

- No data on *what was said* during follow-ups (just outcomes)
- No WhatsApp data — everything was call-based
- Team size was missing for most leads (reduces scoring accuracy)
- Source platform not always filled in
