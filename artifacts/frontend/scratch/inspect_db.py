"""Read-only scratch inspection of the local SQLite schema contents (no writes)."""
import json
import sqlite3
import sys

db = sys.argv[1]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
for bid, active, mj in c.execute("select build_id, active, manifest_json from index_builds"):
    m = json.loads(mj)
    print(bid[:12], active, m.get("strategy"), m.get("dimension"), len(m.get("chunk_ids", [])),
          m.get("created_at"), m["identity"].get("embedding", {}), sorted(m.keys()))
    print("  stats", json.dumps(m.get("statistics"))[:400])
print(c.execute("select count(*), sum(page_type='pdf') from documents").fetchone())
print(c.execute("select build_id, count(*) from chunks group by build_id").fetchall())
print(c.execute("select name, value from metadata").fetchall())
for row in c.execute("select doc_id, source_url, title, page_type, effective_date, crawled_at, length(normalized_blocks_json) from documents limit 3"):
    print(row)
blob = json.loads(c.execute("select normalized_blocks_json from documents limit 1").fetchone()[0])
print(sorted(blob), [sorted(b) for b in blob["blocks"][:2]])
for row in c.execute("select chunk_id, doc_id, heading_path, source_span_json, token_count, substr(text,1,120) from chunks limit 2"):
    print(row)
