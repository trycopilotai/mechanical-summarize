<!-- Synthetic example: written for this repository. It describes no real team, person, or system. -->

# Weekly update: search latency

## What changed

We finally shipped the new cache for search results, and it is not a full fix. p95 latency went from about 840 milliseconds down to roughly 310 milliseconds, but only for queries that hit the cache, which right now is maybe 60 percent of traffic. The other 40 percent are still just as slow as they were last week. These numbers are from staging, not production, so please take them with a grain of salt until we see real traffic.

## What is next

Next week, if nothing else breaks, the plan is to look at the cold path, meaning the uncached queries, because that is where most of the user complaints come from, at least according to support. I think, and Dana disagrees with me on this, that the index rebuild is the bigger problem, whereas she thinks it is the network hop to the ranking service. Honestly, we just do not know yet. So we will run both experiments in parallel, compare them side by side, and I will post the results in this channel by Friday, assuming the staging cluster is back up by then.
