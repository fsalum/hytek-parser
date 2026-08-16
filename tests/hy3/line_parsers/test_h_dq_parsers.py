import unittest

from hytek_parser.hy3.schemas import (
    ParsedHytekFile, Meet, Team, DisqualificationInfo,
)
from hytek_parser.hy3.enums import DisqualificationCode
from hytek_parser.hy3.line_parsers.d_swimmer_parsers import d1_parser
from hytek_parser.hy3.line_parsers.e_event_parsers import e1_parser, e2_parser
from hytek_parser.hy3.line_parsers.h_dq_parsers import (
    LAST_DQ_SLOT_KEY, h1_parser, h2_parser,
)


def _file_with_entry():
    """A file with one swimmer and one individual event entry, no DQ yet."""
    opts = {"default_country": "USA"}
    file = ParsedHytekFile()
    file.meet = Meet()
    file.meet.last_team = ("FOO", Team("Foo Bar", "FOO", "foo", "", "", "", "", "", "", "", "", "", "", "", {}))
    d_line = "D1M   27Hansen              Mads                                                        10272010 13                             27"
    e_line = "E1M   27HanseXX    50D 11109  0U  0.00 22X   37.41S   37.41S    0.00    0.00  0NN               N                               70"
    file = d1_parser(d_line, file, opts)
    file = e1_parser(e_line, file, opts)
    return file, opts


# A known-good 130-column E2 row (from the reaction-time fixtures). _e2_dq()
# overwrites only the result type (col 3), the time code (col 13 -> a DQ code)
# and the DQ code (cols 14-15), leaving every downstream column aligned.
_E2_BASE = "E2P   38.78L       0  1  3  6  34  0   38.87   38.63    0.00        38.78     0.00 0.5607242026    0                            27"


def _e2_dq(result_type: str, dq_code: str, time_code: str = "Q") -> str:
    line = list(_E2_BASE)
    line[2] = result_type          # col 3: P / S / F
    line[12] = time_code           # col 13: 'Q'/'F'/'D' — any is_dq_code value
    line[13], line[14] = dq_code[0], dq_code[1]  # cols 14-15: DQ code
    out = "".join(line)
    assert len(out) == 130
    return out


class TestH1DqParser(unittest.TestCase):
    """h1_parser attaches the DQ reason string to the slot the preceding E2/F2
    result line anchored (opts[LAST_DQ_SLOT_KEY]), not by DQ-code matching."""

    def test_h1_sets_reason_on_anchored_slot(self) -> None:
        file, opts = _file_with_entry()
        entry = file.meet.last_event[1].last_entry
        entry.finals_dq_info = DisqualificationInfo(DisqualificationCode.FLY_KICK_ALTERNATING, "")
        opts[LAST_DQ_SLOT_KEY] = "finals_dq_info"
        result = h1_parser("H11AAlternating Kick", file, opts)
        self.assertEqual("Alternating Kick", result.meet.last_event[1].last_entry.finals_dq_info.info_str)

    def test_h1_no_anchor_is_noop(self) -> None:
        # No result line anchored a slot (opts key absent) → no-op, never raise.
        file, opts = _file_with_entry()
        entry = file.meet.last_event[1].last_entry
        entry.finals_dq_info = DisqualificationInfo(DisqualificationCode.FLY_KICK_ALTERNATING, "")
        result = h1_parser("H11AAlternating Kick", file, opts)  # must not raise
        # Reason left untouched (the seeded empty string), not overwritten.
        self.assertEqual("", result.meet.last_event[1].last_entry.finals_dq_info.info_str)

    def test_h1_anchored_slot_unpopulated_is_noop(self) -> None:
        # Anchor names a slot the entry never populated (e.g. an orphaned H1) →
        # no-op, never raise.
        file, opts = _file_with_entry()
        opts[LAST_DQ_SLOT_KEY] = "finals_dq_info"
        result = h1_parser("H11AAlternating Kick", file, opts)  # must not raise
        entry = result.meet.last_event[1].last_entry
        self.assertIsNone(entry.finals_dq_info)

    def test_h1_leaves_anchor_for_following_h2(self) -> None:
        # h1 must not clear the anchor: the H2 detail line that follows attaches
        # to the same slot.
        file, opts = _file_with_entry()
        entry = file.meet.last_event[1].last_entry
        entry.prelim_dq_info = DisqualificationInfo(DisqualificationCode.FLY_TOUCH_NO_TOUCH, "")
        opts[LAST_DQ_SLOT_KEY] = "prelim_dq_info"
        file = h1_parser("H11MNo touch - fly", file, opts)
        self.assertEqual("prelim_dq_info", opts[LAST_DQ_SLOT_KEY])


class TestH2DqParser(unittest.TestCase):
    """h2_parser attaches the human-readable detail to the same anchored slot."""

    def test_h2_sets_detail_on_anchored_slot(self) -> None:
        file, opts = _file_with_entry()
        entry = file.meet.last_event[1].last_entry
        entry.finals_dq_info = DisqualificationInfo(DisqualificationCode.FLY_KICK_ALTERNATING, "Stroke Infraction swimmer #1")
        opts[LAST_DQ_SLOT_KEY] = "finals_dq_info"
        result = h2_parser("H21AAlternating Kick - fly", file, opts)
        self.assertEqual("Alternating Kick - fly", result.meet.last_event[1].last_entry.finals_dq_info.info_str_detail)

    def test_h2_no_anchor_is_noop(self) -> None:
        file, opts = _file_with_entry()
        result = h2_parser("H21AAlternating Kick - fly", file, opts)  # must not raise
        entry = result.meet.last_event[1].last_entry
        self.assertIsNone(entry.finals_dq_info)

    def test_h2_sets_detail_on_prelim_slot(self) -> None:
        file, opts = _file_with_entry()
        entry = file.meet.last_event[1].last_entry
        entry.prelim_dq_info = DisqualificationInfo(DisqualificationCode.FLY_KICK_ALTERNATING, "Stroke Infraction swimmer #1")
        opts[LAST_DQ_SLOT_KEY] = "prelim_dq_info"
        result = h2_parser("H21AAlternating Kick - fly", file, opts)
        entry = result.meet.last_event[1].last_entry
        self.assertEqual("Alternating Kick - fly", entry.prelim_dq_info.info_str_detail)
        self.assertIsNone(entry.finals_dq_info)

    def test_h2_empty_detail_is_none(self) -> None:
        file, opts = _file_with_entry()
        entry = file.meet.last_event[1].last_entry
        entry.finals_dq_info = DisqualificationInfo(DisqualificationCode.FLY_KICK_ALTERNATING, "Stroke Infraction swimmer #1")
        opts[LAST_DQ_SLOT_KEY] = "finals_dq_info"
        line = "H21A" + " " * 126  # detail region (cols 5+) is blank
        result = h2_parser(line, file, opts)
        entry = result.meet.last_event[1].last_entry
        self.assertIsNone(entry.finals_dq_info.info_str_detail)


class TestDoubleDqEndToEnd(unittest.TestCase):
    """A swim DQ'd in both prelims and finals resolves to ONE shared entry with
    two populated slots. The E2 result line preceding each round's H1/H2 anchors
    those detail lines to the correct slot — the fix's whole point. These drive
    the real e2_parser so the anchor is set by production code, not the test."""

    def test_different_code_double_dq_routes_each_round(self) -> None:
        file, opts = _file_with_entry()
        # Records arrive finals-first, then prelim, each as E2 -> H1 -> H2.
        file = e2_parser(_e2_dq("F", "7T"), file, opts)      # finals DQ 7T
        file = h1_parser("H17TOther - Misc", file, opts)
        file = h2_parser("H27TFinals detail text", file, opts)
        file = e2_parser(_e2_dq("P", "1M"), file, opts)      # prelim DQ 1M
        file = h1_parser("H11MNo touch - fly", file, opts)
        file = h2_parser("H21MPrelim detail text", file, opts)

        entry = file.meet.last_event[1].last_entry
        self.assertEqual("Other - Misc", entry.finals_dq_info.info_str)
        self.assertEqual("Finals detail text", entry.finals_dq_info.info_str_detail)
        self.assertEqual("No touch - fly", entry.prelim_dq_info.info_str)
        self.assertEqual("Prelim detail text", entry.prelim_dq_info.info_str_detail)

    def test_same_code_double_dq_routes_each_round(self) -> None:
        # The reviewer's case: a false start in BOTH prelims and finals gives the
        # two slots the SAME DQ code. Code-matching cannot tell them apart; file
        # position (the anchoring E2 line) can.
        file, opts = _file_with_entry()
        file = e2_parser(_e2_dq("F", "7A", time_code="F"), file, opts)   # finals false start
        file = h1_parser("H17AFalse start - finals", file, opts)
        file = h2_parser("H27AFalse start detail finals", file, opts)
        file = e2_parser(_e2_dq("P", "7A", time_code="F"), file, opts)   # prelim false start
        file = h1_parser("H17AFalse start - prelim", file, opts)
        file = h2_parser("H27AFalse start detail prelim", file, opts)

        entry = file.meet.last_event[1].last_entry
        self.assertEqual("False start - finals", entry.finals_dq_info.info_str)
        self.assertEqual("False start detail finals", entry.finals_dq_info.info_str_detail)
        self.assertEqual("False start - prelim", entry.prelim_dq_info.info_str)
        self.assertEqual("False start detail prelim", entry.prelim_dq_info.info_str_detail)

    def test_non_dq_result_clears_anchor(self) -> None:
        # A DQ finals result anchors its slot; a following clean prelim result must
        # clear the anchor so an orphaned prelim H1 does not attach to the finals
        # reason.
        file, opts = _file_with_entry()
        file = e2_parser(_e2_dq("F", "7T"), file, opts)
        self.assertEqual("finals_dq_info", opts[LAST_DQ_SLOT_KEY])
        # Clean prelim result (_E2_BASE's time code at col 13 is a normal ' ').
        file = e2_parser(_E2_BASE, file, opts)
        self.assertIsNone(opts[LAST_DQ_SLOT_KEY])


if __name__ == "__main__":
    unittest.main()
