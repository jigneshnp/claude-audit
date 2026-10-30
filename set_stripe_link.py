#!/usr/bin/env python3
"""
set_stripe_link.py — Wire your live Stripe Payment Link across the entire
ClaudeCodeAudit monetization kit in one command.

Usage:
    ./set_stripe_link.py https://buy.stripe.com/YOUR_LIVE_LINK [https://buy.stripe.com/YOUR_TEAM_LINK]

If only one link is provided, it is applied to all checkout buttons and outreach drafts.
"""
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
TARGETS = [
    BASE / "landing.html",
    BASE / "index.html",
    BASE / "outreach_ready_to_send.md",
    Path("/Users/jig/Documents/resume/Team_Rejection_Audit_and_Money_Plan.md"),
]

PLACEHOLDER_RE = re.compile(r"https://(?:buy|checkout)\.stripe\.com/[^\s\"')>\]]+")


def main():
    if len(sys.argv) < 2 or not sys.argv[1].startswith("https://"):
        sys.exit("Usage: ./set_stripe_link.py https://buy.stripe.com/YOUR_LIVE_LINK [team_link]")

    primary_link = sys.argv[1].strip()
    team_link = sys.argv[2].strip() if len(sys.argv) >= 3 else primary_link

    updated = []
    for p in TARGETS:
        if not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8")
        if p.name in ("landing.html", "index.html"):
            txt_new = re.sub(
                r'href="https://(?:buy|checkout)\.stripe\.com/[^"]+"(\s+data-stripe-checkout="fast-track")',
                f'href="{primary_link}"\\1',
                txt,
            )
            txt_new = re.sub(
                r'href="https://(?:buy|checkout)\.stripe\.com/[^"]+"(\s+data-stripe-checkout="team-tier")',
                f'href="{team_link}"\\1',
                txt_new,
            )
        else:
            txt_new = PLACEHOLDER_RE.sub(primary_link, txt)

        p.write_text(txt_new, encoding="utf-8")
        updated.append(str(p))

    print(f"Wired Stripe link ({primary_link}) across {len(updated)} files:")
    for u in updated:
        print(f"  - {u}")


if __name__ == "__main__":
    main()
