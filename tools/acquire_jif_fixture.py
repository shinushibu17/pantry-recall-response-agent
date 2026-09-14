"""Pin the selected Jif enforcement record, FDA-linked archived notice, and FDA guidance."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from tools.acquire_fixture import AcquisitionError, fetch, notice_text


ORIGINAL_NOTICE = "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/j-m-smucker-co-issues-voluntary-recall-select-jifr-products-sold-us-potential-salmonella"
NOTICE = "https://web.archive.org/web/20250317210310/" + ORIGINAL_NOTICE
INVESTIGATION = "https://www.fda.gov/food/outbreaks-foodborne-illness/outbreak-investigation-salmonella-peanut-butter-may-2022"
QUERY = {"search": 'recall_initiation_date:[20220501 TO 20220531] AND recall_number:"F-1107-2022"',
         "sort": "recall_initiation_date:asc", "limit": 2}


def acquire(destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    state = {"state": "UNAVAILABLE", "query": QUERY, "page_limit": 1,
             "notice_original_url": ORIGINAL_NOTICE,
             "notice_archive_basis": "The live FDA investigation page links this exact March 17, 2025 archive capture as Recall Announcement.",
             "replay_limit": "Retrospective evidence snapshot, including later FDA guidance and an archived corrected company notice; not knowledge as of May 20, 2022."}
    try:
        raw, state["enforcement"] = fetch("https://api.fda.gov/food/enforcement.json?" + urlencode(QUERY))
        (destination / "enforcement.json").write_bytes(raw)
        data = json.loads(raw)
        if data["meta"]["results"]["total"] != 1 or len(data["results"]) != 1:
            raise AcquisitionError("SELECTION_REQUIRES_REVIEW", "Expected exactly the pinned record, without truncation")
        record = data["results"][0]
        if record["recall_number"] != "F-1107-2022" or record["event_id"] != "90255":
            raise AcquisitionError("SELECTION_REQUIRES_REVIEW", "Pinned recall identifiers changed")
        for name, url in [("notice", NOTICE), ("investigation", INVESTIGATION)]:
            raw, state[name] = fetch(url)
            (destination / (name + ".html")).write_bytes(raw)
            derived = notice_text(raw).encode("utf-8")
            (destination / (name + ".txt")).write_bytes(derived)
            state[name + "_text_sha256"] = hashlib.sha256(derived).hexdigest()
        state.update(state="AVAILABLE", record_identifiers={"recall_number": record["recall_number"], "event_id": record["event_id"]},
                     source_timestamps={"api_last_updated": data["meta"]["last_updated"], "report_date": record["report_date"],
                                        "recall_initiation_date": record["recall_initiation_date"], "company_announcement_date": "2022-05-20",
                                        "fda_publish_date": "2022-05-20", "notice_archive_capture": "2025-03-17T21:03:10Z",
                                        "investigation_includes_later_update": "2023-01-24"})
    except (AcquisitionError, ValueError, KeyError) as error:
        state.update(state=getattr(error, "state", "UNAVAILABLE"), error=str(error))
    (destination / "acquisition.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    result = acquire(parser.parse_args().destination)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["state"] == "AVAILABLE" else 2)
