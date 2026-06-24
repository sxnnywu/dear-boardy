"""Notion target IDs for the persist step (Phase 2 → "Persist to Notion").

Notion is the presentation surface, not the datastore — the pipeline recomputes
Themes + Opportunities from the local `tagged.jsonl` each run and **upserts** them
into the data sources below. These IDs are workspace object identifiers, not
secrets (access is gated by the Notion MCP auth), so they're safe to commit.

Persist writes rows into the DATA SOURCES (the `collection://<id>` targets).
The dashboard's inline tables on the hub are *linked views* of these same data
sources, so they update automatically — never write to a view.
"""

# Project hub (the product surface — holds the inline Dashboard section).
HUB_PAGE_ID = "3894ac696ceb8103999fd703eebe805f"

# Themes database — one row per recurring theme, recomputed each run.
THEMES_DB_PAGE_ID = "043769c9a1b54a198f2b3240cd1b2b00"
THEMES_DATA_SOURCE_ID = "cce36284-e56e-4151-be93-ccf055c4ed49"

# Opportunities database — derived from clustered themes; linked back via relation.
OPPORTUNITIES_DB_PAGE_ID = "65fd73d3582b453e811b5723aa5a149e"
OPPORTUNITIES_DATA_SOURCE_ID = "4f2374c5-2849-4c02-9ea8-e834b56bf081"

# Convenience: the `collection://` form the Notion MCP tools expect.
THEMES_COLLECTION = f"collection://{THEMES_DATA_SOURCE_ID}"
OPPORTUNITIES_COLLECTION = f"collection://{OPPORTUNITIES_DATA_SOURCE_ID}"
