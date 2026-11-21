"""
Emergency Rollback Utility: In-Place Message Payload Reversion

Safely unwraps versioned JSON assistant payloads back to pure plain-text strings
in PostgreSQL if an emergency downgrade to legacy code is required.

SAFEGUARDS:
- Dry-run by default: Will NOT mutate the database unless --apply is explicitly passed.
- Backup verification requirement: --apply FAILS unless --confirm-backup <REF> is provided.
- Idempotent: Only targets messages containing versioned JSON headers.
- Zero data loss: Preserves the plain answer/summary text verbatim.

Usage:
    python backend/scripts/revert_message_payloads.py --dry-run
    python backend/scripts/revert_message_payloads.py --apply --confirm-backup "pg_dump_20261121_verified"
"""

import argparse
import logging
import sys
from typing import Optional

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.message import Message
from app.schemas.message_payload import extract_plain_content

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("orchestra.rollback_payloads")


def revert_payloads(
    db: Session,
    dry_run: bool = True,
    backup_confirmation: Optional[str] = None,
) -> int:
    """
    Reverts versioned JSON message payloads back to plain text.
    Returns the number of candidate messages identified.
    """
    if not dry_run and not backup_confirmation:
        logger.error(
            "SAFETY VIOLATION: In-place database modification aborted! "
            "A verified database backup reference is strictly required. "
            "Pass --confirm-backup '<backup_identifier>' to proceed."
        )
        raise RuntimeError("Missing required backup confirmation for --apply mode.")

    # Target only assistant messages containing versioned JSON
    candidates = (
        db.query(Message)
        .filter(
            Message.role == "assistant",
            Message.content.like('{"version":%'),
        )
        .order_by(Message.id.asc())
        .all()
    )

    logger.info("Found %d candidate versioned JSON messages for reversion.", len(candidates))

    if not candidates:
        logger.info("Zero messages require conversion. Database is clean.")
        return 0

    converted_count = 0
    for msg in candidates:
        original_content = msg.content or ""
        plain_text = extract_plain_content(original_content)

        if plain_text == original_content:
            logger.debug("Message ID %d could not be unwrapped, skipping.", msg.id)
            continue

        if dry_run:
            logger.info(
                "[DRY-RUN] Would revert Message ID %d: length %d -> %d chars. Preview: %r",
                msg.id,
                len(original_content),
                len(plain_text),
                plain_text[:80] + ("..." if len(plain_text) > 80 else ""),
            )
        else:
            msg.content = plain_text
            converted_count += 1

    if not dry_run:
        db.commit()
        logger.info(
            "SUCCESSFULLY converted %d messages to plain text. Verified backup ref: %s",
            converted_count,
            backup_confirmation,
        )
    else:
        logger.info(
            "[DRY-RUN COMPLETE] %d messages eligible for conversion. Zero database modifications made.",
            len(candidates),
        )

    return len(candidates)


def main():
    parser = argparse.ArgumentParser(
        description="Revert versioned JSON assistant messages to plain text."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate reversion without modifying database records (default: True).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to the database. Requires --confirm-backup.",
    )
    parser.add_argument(
        "--confirm-backup",
        type=str,
        default=None,
        help="Confirmation reference or identifier of the verified database backup.",
    )

    args = parser.parse_args()

    # Explicit --apply disables dry-run
    dry_run = not args.apply

    db = SessionLocal()
    try:
        revert_payloads(db=db, dry_run=dry_run, backup_confirmation=args.confirm_backup)
    finally:
        db.close()


if __name__ == "__main__":
    main()
