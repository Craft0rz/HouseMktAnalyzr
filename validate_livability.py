import asyncio, asyncpg, json, os
from dotenv import load_dotenv

load_dotenv('C:/Users/mfont/projects/HouseMktAnalyzr/backend/.env')
DATABASE_URL = os.environ.get("DATABASE_URL")


async def main():
    conn = await asyncpg.connect(DATABASE_URL, ssl="prefer")
    SEP = "=" * 80
    DASH = "-" * 80
    print(SEP)
    print("  HOUSEMKTANALYZR - LIVABILITY DATA VALIDATION REPORT (HOUSE LISTINGS)")
    print(SEP)

    total = await conn.fetchval("SELECT COUNT(*) FROM properties WHERE property_type = $1", "HOUSE")
    print(f"\nTotal HOUSE listings in database: {total}")
    if total == 0:
        print("No HOUSE listings found. Exiting.")
        await conn.close()
        return

    print(f"\n{DASH}")
    print("1. WALK SCORE - Population and Distribution")
    print(DASH)
    ws_count = await conn.fetchval("SELECT COUNT(*) FROM properties WHERE property_type = $1 AND (data->>'walk_score') IS NOT NULL", "HOUSE")
    ws_missing = total - ws_count
    pct_ws = ws_count / total * 100
    print(f"   Houses WITH walk_score:    {ws_count:>6}  ({pct_ws:.1f}%)")
    print(f"   Houses WITHOUT walk_score: {ws_missing:>6}  ({100-pct_ws:.1f}%)")

    ws_dist = await conn.fetch("""
        SELECT
            CASE
                WHEN (data->>'walk_score')::int >= 90 THEN '90-100 (Walkers Paradise)'
                WHEN (data->>'walk_score')::int >= 70 THEN '70-89  (Very Walkable)'
                WHEN (data->>'walk_score')::int >= 50 THEN '50-69  (Somewhat Walkable)'
                WHEN (data->>'walk_score')::int >= 25 THEN '25-49  (Car-Dependent)'
                ELSE                                       '0-24   (Almost All Errands Need Car)'
            END AS bucket,
            COUNT(*) AS cnt,
            ROUND(AVG((data->>'walk_score')::int), 1) AS avg_ws,
            MIN((data->>'walk_score')::int) AS min_ws,
            MAX((data->>'walk_score')::int) AS max_ws
        FROM properties
        WHERE property_type = 'HOUSE' AND (data->>'walk_score') IS NOT NULL
        GROUP BY 1 ORDER BY min_ws DESC
    """)
    if ws_dist:
        print(f'\n   {"Bucket":<42} {"Count":>6}  {"Avg":>5}  {"Min":>4}  {"Max":>4}')
        print(f'   {"-"*42} {"-"*6}  {"-"*5}  {"-"*4}  {"-"*4}')
        for r in ws_dist:
            print(f'   {r["bucket"]:<42} {r["cnt"]:>6}  {r["avg_ws"]:>5}  {r["min_ws"]:>4}  {r["max_ws"]:>4}')

    ws_stats = await conn.fetchrow("""
        SELECT
            ROUND(AVG((data->>'walk_score')::int), 1) AS avg_ws,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (data->>'walk_score')::int) AS median_ws,
            MIN((data->>'walk_score')::int) AS min_ws,
            MAX((data->>'walk_score')::int) AS max_ws
        FROM properties
        WHERE property_type = 'HOUSE' AND (data->>'walk_score') IS NOT NULL
    """)
    if ws_stats and ws_stats["avg_ws"] is not None:
        print(f'\n   Overall:  avg={ws_stats["avg_ws"]}  median={ws_stats["median_ws"]:.0f}  min={ws_stats["min_ws"]}  max={ws_stats["max_ws"]}')

    print(f"\n{DASH}")
    print("2. TRANSIT SCORE - Population and Distribution")
    print(DASH)
    ts_count = await conn.fetchval("SELECT COUNT(*) FROM properties WHERE property_type = $1 AND (data->>'transit_score') IS NOT NULL", "HOUSE")
    ts_missing = total - ts_count
    pct_ts = ts_count / total * 100
    print(f"   Houses WITH transit_score:    {ts_count:>6}  ({pct_ts:.1f}%)")
    print(f"   Houses WITHOUT transit_score: {ts_missing:>6}  ({100-pct_ts:.1f}%)")

    ts_dist = await conn.fetch("""
        SELECT
            CASE
                WHEN (data->>'transit_score')::int >= 90 THEN '90-100 (Excellent Transit)'
                WHEN (data->>'transit_score')::int >= 70 THEN '70-89  (Excellent Transit)'
                WHEN (data->>'transit_score')::int >= 50 THEN '50-69  (Good Transit)'
                WHEN (data->>'transit_score')::int >= 25 THEN '25-49  (Some Transit)'
                ELSE                                          '0-24   (Minimal Transit)'
            END AS bucket,
            COUNT(*) AS cnt,
            ROUND(AVG((data->>'transit_score')::int), 1) AS avg_ts,
            MIN((data->>'transit_score')::int) AS min_ts,
            MAX((data->>'transit_score')::int) AS max_ts
        FROM properties
        WHERE property_type = 'HOUSE' AND (data->>'transit_score') IS NOT NULL
        GROUP BY 1 ORDER BY min_ts DESC
    """)
    if ts_dist:
        print(f'\n   {"Bucket":<42} {"Count":>6}  {"Avg":>5}  {"Min":>4}  {"Max":>4}')
        print(f'   {"-"*42} {"-"*6}  {"-"*5}  {"-"*4}  {"-"*4}')
        for r in ts_dist:
            print(f'   {r["bucket"]:<42} {r["cnt"]:>6}  {r["avg_ts"]:>5}  {r["min_ts"]:>4}  {r["max_ts"]:>4}')

    ts_stats = await conn.fetchrow("""
        SELECT
            ROUND(AVG((data->>'transit_score')::int), 1) AS avg_ts,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (data->>'transit_score')::int) AS median_ts,
            MIN((data->>'transit_score')::int) AS min_ts,
            MAX((data->>'transit_score')::int) AS max_ts
        FROM properties
        WHERE property_type = 'HOUSE' AND (data->>'transit_score') IS NOT NULL
    """)
    if ts_stats and ts_stats["avg_ts"] is not None:
        print(f'\n   Overall:  avg={ts_stats["avg_ts"]}  median={ts_stats["median_ts"]:.0f}  min={ts_stats["min_ts"]}  max={ts_stats["max_ts"]}')

    print(f"\n{DASH}")
    print("3. GEO ENRICHMENT - Population (safety_score, nearest_elementary_m, park_count_1km)")
    print(DASH)
    geo_count = await conn.fetchval("""
        SELECT COUNT(*) FROM properties
        WHERE property_type = 'HOUSE'
          AND (data->'raw_data'->'geo_enrichment') IS NOT NULL
    """)
    geo_missing = total - geo_count
    pct_geo = geo_count / total * 100
    print(f"   Houses WITH geo_enrichment:    {geo_count:>6}  ({pct_geo:.1f}%)")
    print(f"   Houses WITHOUT geo_enrichment: {geo_missing:>6}  ({100-pct_geo:.1f}%)")

    geo_sub = await conn.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE (data->'raw_data'->'geo_enrichment'->>'safety_score') IS NOT NULL) AS has_safety,
            COUNT(*) FILTER (WHERE (data->'raw_data'->'geo_enrichment'->>'nearest_elementary_m') IS NOT NULL) AS has_school,
            COUNT(*) FILTER (WHERE (data->'raw_data'->'geo_enrichment'->>'park_count_1km') IS NOT NULL) AS has_parks
        FROM properties
        WHERE property_type = 'HOUSE'
          AND (data->'raw_data'->'geo_enrichment') IS NOT NULL
    """)
    if geo_sub and geo_count > 0:
        print(f"\n   Among {geo_count} houses WITH geo_enrichment:")
        print(f'     safety_score populated:          {geo_sub["has_safety"]:>6}  ({geo_sub["has_safety"]/geo_count*100:.1f}%)')
        print(f'     nearest_elementary_m populated:   {geo_sub["has_school"]:>5}  ({geo_sub["has_school"]/geo_count*100:.1f}%)')
        print(f'     park_count_1km populated:        {geo_sub["has_parks"]:>6}  ({geo_sub["has_parks"]/geo_count*100:.1f}%)')

    print(f"\n{DASH}")
    print("4. COORDINATES - Valid vs Missing")
    print(DASH)
    coord_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE
                (data->>'latitude') IS NOT NULL
                AND (data->>'longitude') IS NOT NULL
                AND (data->>'latitude')::float BETWEEN 44.0 AND 63.0
                AND (data->>'longitude')::float BETWEEN -80.0 AND -56.0
            ) AS valid_coords,
            COUNT(*) FILTER (WHERE
                (data->>'latitude') IS NULL OR (data->>'longitude') IS NULL
            ) AS null_coords,
            COUNT(*) FILTER (WHERE
                (data->>'latitude') IS NOT NULL
                AND (data->>'longitude') IS NOT NULL
                AND NOT (
                    (data->>'latitude')::float BETWEEN 44.0 AND 63.0
                    AND (data->>'longitude')::float BETWEEN -80.0 AND -56.0
                )
            ) AS invalid_coords
        FROM properties
        WHERE property_type = 'HOUSE'
    """)
    if coord_stats:
        print(f'   Valid coordinates (Quebec bbox):  {coord_stats["valid_coords"]:>6}  ({coord_stats["valid_coords"]/total*100:.1f}%)')
        print(f'   NULL coordinates:                 {coord_stats["null_coords"]:>6}  ({coord_stats["null_coords"]/total*100:.1f}%)')
        print(f'   Invalid/out-of-range:             {coord_stats["invalid_coords"]:>6}  ({coord_stats["invalid_coords"]/total*100:.1f}%)')

    print(f"\n{DASH}")
    print("5. WALK SCORE ATTEMPTED (tried but failed)")
    print(DASH)
    ws_attempted = await conn.fetchval("SELECT COUNT(*) FROM properties WHERE property_type = $1 AND (data->>'walk_score_attempted_at') IS NOT NULL", "HOUSE")
    ws_attempted_no_score = await conn.fetchval("SELECT COUNT(*) FROM properties WHERE property_type = $1 AND (data->>'walk_score_attempted_at') IS NOT NULL AND (data->>'walk_score') IS NULL", "HOUSE")
    print(f"   walk_score_attempted_at SET:               {ws_attempted}")
    print(f"     of which walk_score IS NULL (failed):     {ws_attempted_no_score}")
    print(f"     of which walk_score IS NOT NULL (success): {ws_attempted - ws_attempted_no_score}")

    print(f"\n{DASH}")
    print("6. GEOCODE FAILED")
    print(DASH)
    gc_failed = await conn.fetchval("SELECT COUNT(*) FROM properties WHERE property_type = $1 AND (data->>'geocode_failed_at') IS NOT NULL", "HOUSE")
    print(f"   Houses with geocode_failed_at SET: {gc_failed}")

    print(f"\n{DASH}")
    print("7. SAMPLE: 10 Houses WITH Walk Scores")
    print(DASH)
    with_ws = await conn.fetch("""
        SELECT
            id, city,
            (data->>'walk_score')::int AS walk_score,
            (data->>'transit_score')::int AS transit_score,
            (data->'raw_data'->'geo_enrichment'->>'safety_score') AS safety_score,
            (data->'raw_data'->'geo_enrichment'->>'nearest_elementary_m') AS nearest_elem_m,
            (data->'raw_data'->'geo_enrichment'->>'park_count_1km') AS park_count_1km,
            (data->>'latitude') AS lat,
            (data->>'longitude') AS lon
        FROM properties
        WHERE property_type = 'HOUSE' AND (data->>'walk_score') IS NOT NULL
        ORDER BY RANDOM() LIMIT 10
    """)
    if with_ws:
        print(f'\n   {"ID":<14} {"City":<18} {"WS":>4} {"TS":>4} {"Safety":>7} {"School_m":>9} {"Parks":>5} {"Lat":>9} {"Lon":>10}')
        print(f'   {"-"*14} {"-"*18} {"-"*4} {"-"*4} {"-"*7} {"-"*9} {"-"*5} {"-"*9} {"-"*10}')
        for r in with_ws:
            ws = r["walk_score"] if r["walk_score"] is not None else "-"
            ts = r["transit_score"] if r["transit_score"] is not None else "-"
            ss = r["safety_score"] if r["safety_score"] else "-"
            ne = r["nearest_elem_m"] if r["nearest_elem_m"] else "-"
            pk = r["park_count_1km"] if r["park_count_1km"] else "-"
            lat = str(r["lat"])[:9] if r["lat"] else "-"
            lon = str(r["lon"])[:10] if r["lon"] else "-"
            print(f'   {str(r["id"])[:14]:<14} {str(r["city"] or "-")[:18]:<18} {ws:>4} {ts:>4} {ss:>7} {ne:>9} {pk:>5} {lat:>9} {lon:>10}')
    else:
        print("   (no results)")

    print(f"\n{DASH}")
    print("8. SAMPLE: 10 Houses WITHOUT Walk Scores")
    print(DASH)
    without_ws = await conn.fetch("""
        SELECT
            id, (data->>'address') AS address, city,
            (data->>'latitude') AS lat, (data->>'longitude') AS lon,
            (data->>'walk_score_attempted_at') AS ws_attempted,
            (data->>'geocode_failed_at') AS gc_failed
        FROM properties
        WHERE property_type = 'HOUSE' AND (data->>'walk_score') IS NULL
        ORDER BY RANDOM() LIMIT 10
    """)
    if without_ws:
        print(f'\n   {"ID":<14} {"Address":<32} {"City":<14} {"Lat":>9} {"Lon":>10} {"WS_Attempted":<22} {"GC_Failed":<22}')
        print(f'   {"-"*14} {"-"*32} {"-"*14} {"-"*9} {"-"*10} {"-"*22} {"-"*22}')
        for r in without_ws:
            addr = str(r["address"] or "-")[:31]
            lat = str(r["lat"] or "-")[:9]
            lon = str(r["lon"] or "-")[:10]
            ws_a = str(r["ws_attempted"] or "-")[:21]
            gc_f = str(r["gc_failed"] or "-")[:21]
            print(f'   {str(r["id"])[:14]:<14} {addr:<32} {str(r["city"] or "-")[:14]:<14} {lat:>9} {lon:>10} {ws_a:<22} {gc_f:<22}')
    else:
        print("   (no results)")

    print(f"\n{DASH}")
    print("9. GEO ENRICHMENT SUB-FIELD COUNTS (among houses WITH geo_enrichment)")
    print(DASH)
    if geo_sub and geo_count > 0:
        print(f'   safety_score populated:          {geo_sub["has_safety"]:>6} / {geo_count}')
        print(f'   nearest_elementary_m populated:   {geo_sub["has_school"]:>5} / {geo_count}')
        print(f'   park_count_1km populated:        {geo_sub["has_parks"]:>6} / {geo_count}')
    else:
        print("   (no geo_enrichment data found)")

    print(f"\n{DASH}")
    print("10. GEO ENRICHMENT AVERAGES (houses WITH geo_enrichment)")
    print(DASH)
    geo_avgs = await conn.fetchrow("""
        SELECT
            ROUND(AVG((data->'raw_data'->'geo_enrichment'->>'safety_score')::numeric), 2) AS avg_safety,
            ROUND(AVG((data->'raw_data'->'geo_enrichment'->>'nearest_elementary_m')::numeric), 1) AS avg_school_m,
            ROUND(AVG((data->'raw_data'->'geo_enrichment'->>'park_count_1km')::numeric), 2) AS avg_parks
        FROM properties
        WHERE property_type = 'HOUSE'
          AND (data->'raw_data'->'geo_enrichment') IS NOT NULL
    """)
    if geo_avgs:
        print(f'   Average safety_score:          {geo_avgs["avg_safety"] or "N/A"}')
        print(f'   Average nearest_elementary_m:  {geo_avgs["avg_school_m"] or "N/A"}  meters')
        print(f'   Average park_count_1km:        {geo_avgs["avg_parks"] or "N/A"}')

    print(f"\n{DASH}")
    print("SUMMARY CROSS-TAB")
    print(DASH)
    cross = await conn.fetchrow("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE (data->>'walk_score') IS NOT NULL) AS has_ws,
            COUNT(*) FILTER (WHERE (data->>'transit_score') IS NOT NULL) AS has_ts,
            COUNT(*) FILTER (WHERE (data->'raw_data'->'geo_enrichment') IS NOT NULL) AS has_geo,
            COUNT(*) FILTER (WHERE
                (data->>'walk_score') IS NOT NULL
                AND (data->'raw_data'->'geo_enrichment') IS NOT NULL
            ) AS has_ws_and_geo,
            COUNT(*) FILTER (WHERE
                (data->>'walk_score') IS NOT NULL
                AND (data->>'transit_score') IS NOT NULL
                AND (data->'raw_data'->'geo_enrichment') IS NOT NULL
            ) AS has_all_three
        FROM properties
        WHERE property_type = 'HOUSE'
    """)
    if cross:
        t = cross["total"]
        print(f"   Total HOUSE listings:                             {t}")
        print(f'   Has walk_score:                                   {cross["has_ws"]:>5}  ({cross["has_ws"]/t*100:.1f}%)')
        print(f'   Has transit_score:                                {cross["has_ts"]:>5}  ({cross["has_ts"]/t*100:.1f}%)')
        print(f'   Has geo_enrichment:                               {cross["has_geo"]:>5}  ({cross["has_geo"]/t*100:.1f}%)')
        print(f'   Has walk_score + geo_enrichment:                  {cross["has_ws_and_geo"]:>5}  ({cross["has_ws_and_geo"]/t*100:.1f}%)')
        print(f'   Has walk + transit + geo (full livability data):  {cross["has_all_three"]:>5}  ({cross["has_all_three"]/t*100:.1f}%)')

    print(f"\n{SEP}")
    print("  END OF REPORT")
    print(SEP)
    await conn.close()


asyncio.run(main())
