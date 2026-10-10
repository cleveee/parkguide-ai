# Initial diagnostics: semantic review and observed failures

This is a provisional AI review, not a human grade or a formal gold benchmark. The reviewer authored the diagnostic fixtures before any chatbot outputs and reviewed the saved generator outputs independently from generation. Human source verification remains pending.

The review covers all 72 saved diagnostic results (12 questions × six configurations) and 17 attempted dialogue turns (16 delivered responses, one pipeline error). T06 turn 3 was not attempted after the initial runner aborted; it is not an observed success or failure. Full details and per-claim support judgments are in `artifacts/reviews/initial-semantic-review.jsonl`.

A semantically correct result answers the actual question or requests/refuses the appropriate missing information. Its action label is judged separately. Claim support requires at least one cited supplied passage to entail each factual claim; a matching number alone is insufficient. B0 is closed book: citation evaluation is not applicable, and factual claims are checked against the captured corpus. Fractions are qualitative AI judgments, not calibrated measurements.

## Observed result counts

| Group | Reviewed | Correct | Incorrect | Uncertain | Action-label mismatches |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0 | 12 | 7 | 4 | 1 | 0 |
| B1 | 12 | 9 | 3 | 0 | 1 |
| B2 | 12 | 9 | 3 | 0 | 1 |
| B3 | 12 | 9 | 2 | 1 | 1 |
| C1 | 12 | 11 | 1 | 0 | 1 |
| C2 | 12 | 11 | 1 | 0 | 0 |
| Initial dialogues | 17 | 9 | 7 | 1 | 1 |
| Total | 89 | 65 | 21 | 3 | 5 |

There are 21 incorrect delivered results plus one pipeline failure: 22 observed failure instances. These are repeated instances across configurations, not 22 unique root causes. Four additional diagnostic answers correctly abstain in their text but use the wrong action label. The two other uncertain verdicts concern unsupported causal embellishments; they are not asserted to be proven false. This count is based on observed cases, not a target number of failures.

## Actual failures to fix

| Case(s) | Observed behavior | Cause and source evidence | Practical correction |
| --- | --- | --- | --- |
| B0 D001 | Invents campground check-in 1–3 pm and checkout around 11 am. | Both Yosemite FAQ and regulations state noon. | Ground park-specific operating facts in retrieval. |
| B0 D002 | Sets both largest RV and trailer limits to 35 ft. | Yosemite campground page says RV 40 ft, trailer 35 ft, only eight largest sites. | Preserve entity-specific units and limits. |
| B0 D006 | Gives only the 30-inch wheelchair width limit. | Shuttle page also imposes a 48-inch length limit, needed to answer the stated size question. | Return both dimensions. |
| B0 D008 | Gives Desert View Drive length as 25 mi. | Captured NPS source gives 23 mi / 37 km. | Prefer the retrieved route figure. |
| B1 D001; B2 D002/D003; B3 D003; T03/1 | Correct raw answers become quote-limit refusals. | Retrieved facts support the raw answer; excessive copied phrasing triggers the configured guard. | Generate a short paraphrase and reserve refusal for missing evidence; keep raw and delivered outcomes distinct. |
| T02/1 | Guard suppresses a valid 1,140-ft vertical calculation. | Table: South Kaibab rim 7,260 ft; Cedar Ridge 6,120 ft; difference 1,140 ft. The phrase “below the rim” also admits a vertical interpretation even though the fixture expected trail mileage. | Validate arithmetic witnesses, and clarify vertical change versus trail distance in future diagnostic versions. Do not change the frozen first draft silently. |
| T02/2 | Lacks the Cedar Ridge table row and abstains in text while labelling the response answer. | Supplied contexts contain only the DW legend; complete corpus has the blank Cedar Ridge drinking-water column. | Retain concrete place names across pronouns and retrieve the complete relevant table row. |
| T02/3 | Supplies correct endpoint mileages without answering “how much farther.” | 3 mi minus 1.5 mi is a 1.5-mi difference. | State the supported difference explicitly. |
| B1 D011 | Assumes the unknown park is Grand Canyon while asking which item. | The initial question and empty history identify neither object nor park. | Clarify missing referents without letting retrieval invent user intent. |
| B1/B2/B3/C1/C2 D012 | Guesses campground facts or refuses rather than requesting starting location. | “Closest” has no reference location. B1/C2 also repeat an old 2023–2024 Mammoth closure as future/current in a 2026 run. | Clarify the reference point before retrieval; preserve historical qualifiers on old source claims. |
| T04/1 | Answers campground check-in and hiking services for “Can I go in whenever?” | No park, entrance, or date is specified. It also drops the next-day-noon condition on forfeiture. | Ask what entrance/place and time the user means; preserve conditions. |
| T04/2 | Invents Hetch Hetchy entrance hours 9:30 am–5 pm and assigns general snow-road closures to that road. | The brochure explicitly uses the park map as a clock face: Hetch Hetchy at 9:30 is a spatial direction. The 5 pm belongs to Mariposa Grove Depot in an interleaved PDF. The hours page only says “some roads” close seasonally. | Validate the entity, dimension, and relationship attached to each number; retain parent map-description context and PDF layout caveats. |
| T04/3 | Final guard refuses; raw response repeats the unsupported 9:30 am–5 pm entrance schedule. | Daylight is supported; that specific schedule is not. Here the guard prevented an unsupported claim, unlike T02/1. | Answer the simple supported midnight/daylight comparison, without fabricated times. |
| T06/2 | No response delivered: structured validation raises claims_on_nonanswer. | Actual saved PIPELINE_ERROR row. The generator returned a schema-inconsistent nonanswer/claims combination; its exact factual answer is unavailable. | Repair/validate structured output within the bounded retry policy; record each turn error and continue remaining conversations. |
| B1/B2/B3/C1 D010 | Correctly says a specific passport recovery cannot be determined, but action is answer. | Public lost-and-found reporting instructions cannot reveal a private live recovery status. No status is fabricated. | Make semantic abstention use refuse consistently. |

## Correct answers that the lexical metric underscored

The low phrase score alone does not establish error. Thermal-area answers saying children should be kept close and not allowed to run are correct paraphrases. Ranger programs described as year-round answer the question without also quoting the calendar advice. Desert View responses giving 23 mi / 37 km answer its length question without needing to mention the East Entrance. A train response saying no direct train answers that yes/no question even when it omits the optional depot list. Stock-price refusals and passport abstentions remain appropriate when their wording differs from the draft’s expected phrase.

T01 correctly handles the 2025-to-2026 guide change and the switch to Grand Canyon. T03/2 and T03/3 give the correct park-specific bear distances. T05 refuses the private booking lookup and then provides grounded food-storage guidance. T06/1 correctly refuses drone use under Yellowstone’s rule.

## Source and review limitations

The corpus contains conflicting late-arrival deadlines: Yosemite regulations say check in before 10 am the next morning, while the FAQ describes loss of the reservation if there is no contact/check-in by noon. B2/B3/C1/C2 D001 answer the asked check-in/checkout question correctly (noon), but add the 10 am deadline without discussing that conflict. A short answer would avoid this unnecessary unresolved detail.

B0 D003 adds an explanation about “strong bears,” and B3 D005 describes the thermal organisms as harmful to visitors. Those causal additions are not supported by the captured passages; the requested core rules are correct. Their factual truth is uncertain rather than established false.

These results concern the captured static corpus. Current availability, private booking records, real-time queues, and future forecasts were not independently queried. Formal accuracy, citation-support rates, and human-reviewed benchmark claims remain pending.
