<!-- Synthetic example: written for this repository. It describes no real team, person, or system. -->

# Weekly update: search latency

## What changed

This week we finally shipped the new cache for search results, and it is not a full fix. p95 latency went from about 840 milliseconds to roughly 310 milliseconds, but only for queries that hit the cache, right now maybe 60 percent of traffic. The other 40 percent are still as slow as before. These numbers are from staging, not production, so please take them with a grain of salt until we see real traffic.

## What is next

Next week, if nothing else breaks, the plan is to look at the cold path, because that is where most user complaints come from, at least according to support. I think, and Dana disagrees, that the index rebuild is the bigger problem, whereas she thinks it is the network hop to the ranking service. We will run both experiments in parallel, and I will post the results by Friday, assuming the staging cluster is back up.
