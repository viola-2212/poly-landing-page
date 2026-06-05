---
name: plg-launch-update-daily
description: Pull Open Platform PLG launch metrics from Pendo and send to Viola's Slack DM
---

Pull the Open Platform (PLG) launch update from Pendo and send the results to Viola Lin's Slack DM (user ID: U07BKAKK5B7).

## Pendo Configuration
- Subscription ID: 6417582487568384
- App ID: -323232
- Launch date: May 18, 2026
- Launch epoch (firstvisit filter): 1747526400000
- Date range for all activity queries: startDate: 2026-05-18, endDate: today's date

## Filters — Apply to All Queries
PLG external users (visitorMetadataFilter):
  metadata.agent.isplg == true && metadata.agent.usertype == "external"

Sign-up count filter (visitorQuery metadataFilter):
  metadata.agent.isplg == true && metadata.agent.usertype == "external" && metadata.auto.firstvisit >= 1747526400000

NOTE: visitorMetadataFilter and segmentId are mutually exclusive in Pendo — never combine them.

## Internal Exclusions — Remove from all counts, leaderboards, and funnel numbers
- @gammaconsultingllc.com (all users)
- @poly-interview.com (interview candidates)
- aaron.forinton@gmail.com
- milosdstanisavljevic@gmail.com
- account: agent-studio-plg-testing
- account: frank-ws

## Queries to Run

1. NEW SIGN-UPS — visitorQuery, count: true, use sign-up metadataFilter (with firstvisit)
2. ACTIVE WORKSPACES — activityQuery, entityType: account, group: ["accountId"], count: true
3. ACTIVE USERS — activityQuery, entityType: visitor, group: ["visitorId"], count: true
4. FUNNEL (uniqueAccountCount per step):
   a) Created an agent:      O_fLUgbXZZggpIJvGn0yGJbD3VE
   b) Tested via in-app call: mZiBuCH9usNigJVcMUmseIKVNuU
   c) Published to sandbox:  lrDtbogpimUN3j1R3okxxXdyry4
   d) Promoted to live:      kU33LDPOvxQYH_FJASOmo_xe3i8
5. PROMOTE-TO-LIVE USER LIST — activityQuery, entityType: feature, itemIds: ["kU33LDPOvxQYH_FJASOmo_xe3i8"], group: ["visitorId"], sort: ["-numEvents"]
6. TOP ACTIVE USERS — activityQuery, entityType: visitor, group: ["visitorId"], sort: ["-numEvents"], limit: 20 → remove exclusions → take top 10

## Output Format — send exactly this to Slack DM

Open Platform Launch Update — May 18 to [today] (Day [N])
External users only

Headline:
- [X] new external sign-ups since launch
- [X] active external workspaces
- [X] active external users

Funnel (unique external workspaces):
  Sign-ups              [X]
  Created an agent      [X]  ([%])
  Tested via call       [X]  ([%])
  Published to sandbox  [X]  ([%])
  Promoted to live      [X]  ([%])

Percentages are relative to sign-ups.

Promoted to Live — list each user email + domain.

Top Active Users:
| Rank | Email | Domain | Events | Days Active |

Flag notable company domains (non-gmail/outlook).

Previous benchmarks (Day 2 = May 20): Sign-ups: 763 | Agents: 94 | Tested: 73 | Live: 7

## Notes
- Use "Workspaces" not "Visitors" in headlines
- Day N = today minus May 18, 2026
- visitorQuery limit max 50000, activityQuery limit max 1000
- If activityQuery returns "too much data", use count: true or reduce scope
