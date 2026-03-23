"""Google Cloud Function for URL redirect with PII masking.

Translates:
    GET /{jotform_id}/{hash}
into a 302 redirect to:
    https://form.jotform.com/{jotform_id}?parent_name[first]=...&...

Also provides a CLI for testing:
    python main.py --jotform-id <ID> --hash-code <CODE>
"""

import argparse
import json
import logging
import sys
from urllib.parse import urlencode

import functions_framework
from flask import redirect as flask_redirect
from werkzeug import wrappers

from config import get_field_mapping
from database import get_record

logger = logging.getLogger(__name__)


@functions_framework.http
def handle_redirect(request: wrappers.Request) -> wrappers.Response | tuple[str, int]:
    """HTTP Cloud Function entry point.

    Args:
        request: Flask request with path /{jotform_id}/{hash}.

    Returns:
        302 redirect to JotForm with pre-filled personal data,
        or an error response (400/404).
    """
    path = request.path.strip("/")
    parts = path.split("/")

    if len(parts) != 2:
        logger.warning("Invalid URL format: %s", request.path)
        return ("Invalid URL format. Expected: /{jotform_id}/{hash}", 400)

    jotform_id, hash_code = parts

    if not jotform_id.isdigit():
        logger.warning("Invalid form ID: %s", jotform_id)
        return ("Invalid form ID.", 400)

    if not hash_code.isalnum():
        logger.warning("Invalid hash: %s", hash_code)
        return ("Invalid hash.", 400)

    record = get_record(jotform_id, hash_code)
    if record is None:
        logger.info("Record not found: jotform_id=%s, hash=%s", jotform_id, hash_code)
        return ("Odkaz není platný nebo vypršel.", 404)

    fields = get_field_mapping(jotform_id)

    params = {
        fields["parent_first"]: record["parent_first"],
        fields["parent_last"]: record["parent_last"],
        fields["child_first"]: record["child_first"],
        fields["child_last"]: record["child_last"],
    }

    url = f"https://form.jotform.com/{jotform_id}?{urlencode(params)}"
    logger.info("Redirecting hash=%s to form=%s", hash_code, jotform_id)

    return flask_redirect(url, code=302)


def cli() -> None:
    """Command-line interface for testing record lookups."""
    parser = argparse.ArgumentParser(description="Look up a record by jotform_id and hash_code")
    parser.add_argument("--jotform-id", required=True, help="JotForm form ID")
    parser.add_argument("--hash-code", required=True, help="Recipient hash code")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    record = get_record(args.jotform_id, args.hash_code)
    if record is None:
        logger.error("Record not found: jotform_id=%s, hash=%s", args.jotform_id, args.hash_code)
        sys.exit(1)

    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
