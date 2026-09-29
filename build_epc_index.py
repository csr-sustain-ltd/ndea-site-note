#!/usr/bin/env python3
"""
Build the lookup files used by the NDEA Site Note "Previous EPC Check".

Reads the bulk non-domestic download (certificates-YYYY.csv files) and writes
one small JSON file per postcode district, e.g.  epc-data/OL16.json
The site note loads only the file for the postcode being typed.

Usage
    python3 build_epc_index.py  <folder containing certificates-*.csv>  <output folder>
    python3 build_epc_index.py  ./non-domestic-csv  ./epc-data

Re-run whenever you download a fresh bulk file. Only certificates-*.csv is used
(recommendations-*.csv is ignored).

NOTE: this dataset is not openly licensed (it contains Royal Mail address data).
Keep the output folder on private / internal hosting.
"""
import csv, glob, json, os, re, sys, datetime, collections

csv.field_size_limit(10**9)
PC_RE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?) (\d[A-Z]{2})$")


def num(s):
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def compact(x):
    """Whole numbers as ints, keep decimals otherwise, None stays None."""
    if x is None:
        return None
    return int(x) if x == int(x) else round(x, 2)


def main(src, out):
    files = sorted(glob.glob(os.path.join(src, "certificates-*.csv")))
    if not files:
        sys.exit("No certificates-*.csv files found in " + src)
    os.makedirs(out, exist_ok=True)

    shards = collections.defaultdict(list)
    seen = set()
    total = skipped = 0
    newest = ""
    for f in files:
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                total += 1
                pc = (r.get("postcode") or "").strip().upper()
                m = PC_RE.match(pc)
                cert = r.get("certificate_number") or ""
                if not m or not cert or cert in seen:
                    skipped += 1
                    continue
                seen.add(cert)
                rating = num(r.get("asset_rating"))
                if rating is None:
                    skipped += 1
                    continue
                d = (r.get("lodgement_date") or "")[:10]
                newest = max(newest, d)
                addr = (r.get("address") or "").strip()
                if not addr:
                    addr = ", ".join(x for x in (r.get("address1"), r.get("address2"), r.get("address3"), r.get("posttown")) if x)
                shards[m.group(1)].append({
                    "lmk": cert,
                    "uprn": r.get("uprn") or "",
                    "address": addr,
                    "postcode": pc,
                    "assetRating": compact(rating),
                    "band": r.get("asset_rating_band") or "",
                    "floorArea": compact(num(r.get("floor_area"))),
                    "lodgementDate": d,
                    "inspectionDate": (r.get("inspection_date") or "")[:10],
                    "mainHeatingFuel": r.get("main_heating_fuel") or "",
                    "buildingEnvironment": r.get("building_environment") or "",
                    "propertyType": r.get("property_type") or "",
                    "buildingLevel": r.get("building_level") or "",
                    "buildingEmissions": compact(num(r.get("building_emissions"))),
                    "typicalEmissions": compact(num(r.get("typical_emissions"))),
                    "standardEmissions": compact(num(r.get("standard_emissions"))),
                    "renewables": r.get("renewable_sources") or "",
                })
        print("read", os.path.basename(f), flush=True)

    size = 0
    for district, rows in shards.items():
        rows.sort(key=lambda x: x["lodgementDate"], reverse=True)
        payload = {"ok": True, "district": district, "count": len(rows), "results": rows}
        path = os.path.join(out, district + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)
        size += os.path.getsize(path)

    meta = {
        "built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "newestLodgement": newest,
        "certificates": len(seen),
        "districts": len(shards),
        "source": "EPC Register (MHCLG) bulk non-domestic certificates",
    }
    with open(os.path.join(out, "_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print("rows read %d | kept %d | skipped %d | districts %d | %.1f MB uncompressed | newest lodgement %s"
          % (total, len(seen), skipped, len(shards), size / 1e6, newest))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
