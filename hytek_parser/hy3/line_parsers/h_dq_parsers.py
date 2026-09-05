from typing import Any

from hytek_parser._utils import extract
from hytek_parser.hy3.schemas import ParsedHytekFile

# Key under which the E2/F2 result parser records the DQ slot it just populated,
# so the H1 reason line and H2 detail line that immediately follow attach to that
# same slot. A swim DQ'd in both prelims and finals resolves to ONE shared entry
# with two populated slots; the result line preceding each round's H1/H2 in file
# order is the authoritative anchor for which slot those detail lines belong to.
# This holds even when both rounds carry the SAME DQ code (e.g. a false start in
# both prelims and finals): matching on the code alone cannot tell the two slots
# apart, but file position always can.
LAST_DQ_SLOT_KEY = "_last_dq_slot"


def h1_parser(
    line: str, file: ParsedHytekFile, opts: dict[str, Any]
) -> ParsedHytekFile:
    """Parse an H1 line: the DQ reason string, routed to its own DQ slot.

    Attaches the reason to the slot the immediately-preceding E2/F2 result line
    populated (recorded in ``opts`` under ``LAST_DQ_SLOT_KEY``). That result line
    is the authoritative anchor: a swim DQ'd in both prelims and finals carries
    two populated slots on one shared entry, and file position — not the DQ code —
    tells the two H1s apart, including when both rounds share the same code.

    No-op when no slot is anchored or the anchored slot is unpopulated — the DQ
    status and code are recorded by the E2/F2 result line regardless, so only the
    human-readable reason string is ever at stake. Leaves the anchor in place so
    the H2 detail line that follows attaches to the same slot.
    """
    event_num, event = file.meet.last_event
    entry = event.last_entry

    info_str = extract(line, 5, 124)  # Whitespace is stripped

    slot = opts.get(LAST_DQ_SLOT_KEY)
    if slot is not None:
        info = getattr(entry, slot)
        if info is not None:
            info.info_str = info_str

    event.last_entry = entry
    file.meet.last_event = (event_num, event)

    return file


def h2_parser(
    line: str, file: ParsedHytekFile, opts: dict[str, Any]
) -> ParsedHytekFile:
    """Parse an H2 line: the specific, human-readable DQ infraction detail.

    Attaches the detail to the same slot the preceding E2/F2 result line anchored
    (``LAST_DQ_SLOT_KEY``) — the slot h1_parser also wrote to. H2 cannot
    self-identify its slot: its own 2-char code is the stroke/leg infraction (e.g.
    "2L"), not the slot's ``DisqualificationCode`` (e.g. the relay-leg code "6A"),
    so the anchor is the only reliable signal. No-op when no slot is anchored or
    the anchored slot is unpopulated.
    """
    event_num, event = file.meet.last_event
    entry = event.last_entry

    detail = extract(line, 5, 124) or None

    slot = opts.get(LAST_DQ_SLOT_KEY)
    if slot is not None:
        info = getattr(entry, slot)
        if info is not None:
            info.info_str_detail = detail

    event.last_entry = entry
    file.meet.last_event = (event_num, event)
    return file
