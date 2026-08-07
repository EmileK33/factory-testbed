"""Tests for the feed's tag vocabulary."""

from src.parse import KNOWN_TAGS


def test_known_tags_cover_the_feed_vocabulary():
    assert "settled" in KNOWN_TAGS
    assert "crossborder" in KNOWN_TAGS
    assert "priority" in KNOWN_TAGS
    assert len(KNOWN_TAGS) == 12
