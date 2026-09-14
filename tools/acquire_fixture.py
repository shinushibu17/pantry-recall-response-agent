"""Optional one-page acquisition for the Pearl Milling historical fixture.

Never used by the offline replay. Refuses to overwrite an existing snapshot.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


NOTICE_URL = (
    "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/"
    "quaker-issues-limited-recall-undeclared-milk-pearl-milling-company-original-pancake-waffle-mix"
)
QUERY = {
    "search": 'recall_initiation_date:[20250101 TO 20250131] AND product_description:"Pearl Milling"',
    "sort": "recall_initiation_date:asc",
    "limit": 2,
}
ENFORCEMENT_URL = "https://api.fda.gov/food/enforcement.json?" + urlencode(QUERY)


class NoticeText(HTMLParser):
    """Deterministic visible-text derivative; raw HTML remains authoritative."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data)


def notice_text(raw):
    parser = NoticeText()
    parser.feed(raw.decode("utf-8"))
    return " ".join(" ".join(parser.parts).split()) + "\n"


class AcquisitionError(Exception):
    def __init__(self, state, detail):
        self.state = state
        super().__init__(detail)


def fetch(url):
    # One page only, at most three attempts, 20 seconds per request.
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "PantryRecallFixture/0.1"})
            with urlopen(request, timeout=20) as response:
                raw = response.read()
                return raw, {
                    "url": url,
                    "resolved_url": response.url,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "http_date": response.headers.get("Date"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
        except HTTPError as error:
            with error:
                body = error.read().decode("utf-8", errors="replace")
            try:
                api_error = json.loads(body).get("error", {})
            except (ValueError, AttributeError):
                api_error = {}
            if not isinstance(api_error, dict):
                api_error = {}
            if (url.startswith("https://api.fda.gov/") and error.code == 404
                    and api_error.get("code") == "NOT_FOUND"
                    and api_error.get("message") == "No matches found!"):
                raise AcquisitionError("NO_RESULTS", body) from error
            if error.code in {401, 403}:
                raise AcquisitionError("ACCESS_DENIED", f"HTTP {error.code}") from error
            if error.code == 400:
                raise AcquisitionError("INVALID_QUERY", body) from error
            if (error.code == 429 or error.code >= 500) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise AcquisitionError("UNAVAILABLE", f"HTTP {error.code}: {body[:200]}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise AcquisitionError("UNAVAILABLE", str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New snapshot directory")
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=False)
    state = {"state": "UNAVAILABLE", "query": QUERY, "page_limit": 1}
    try:
        enforcement_raw, enforcement_meta = fetch(ENFORCEMENT_URL)
        (args.destination / "enforcement.json").write_bytes(enforcement_raw)
        state["enforcement"] = enforcement_meta
        data = json.loads(enforcement_raw)
        if data["meta"]["results"]["total"] != 1 or len(data["results"]) != 1:
            raise AcquisitionError("SELECTION_REQUIRES_REVIEW", "Expected exactly one record; no additional pages fetched")
        record = data["results"][0]
        if record["recall_number"] != "F-0553-2025":
            raise AcquisitionError("SELECTION_REQUIRES_REVIEW", "Historical record identifier changed")
        notice_raw, notice_meta = fetch(NOTICE_URL)
        (args.destination / "notice.html").write_bytes(notice_raw)
        derived = notice_text(notice_raw).encode("utf-8")
        (args.destination / "notice.txt").write_bytes(derived)
        state.update({
            "state": "AVAILABLE",
            "notice": notice_meta,
            "notice_text_sha256": hashlib.sha256(derived).hexdigest(),
            "record_identifiers": {"recall_number": record["recall_number"], "event_id": record["event_id"]},
            "source_timestamps": {
                "api_last_updated": data["meta"]["last_updated"],
                "report_date": record["report_date"],
                "recall_initiation_date": record["recall_initiation_date"],
                "company_announcement_date": "2025-01-14",
                "fda_publish_date": "2025-01-15",
            },
        })
    except (AcquisitionError, ValueError, KeyError) as error:
        state.update({"state": getattr(error, "state", "UNAVAILABLE"), "error": str(error)})
    (args.destination / "acquisition.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2))
    return 0 if state["state"] == "AVAILABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
