"""Unit tests for the Items domain model."""

import pytest
from items.domain.events import ItemCreated, ItemUpdated
from items.domain.model import Item
from items.domain.value_objects import Description, Name


class TestName:
    def test_accepts_valid_value(self):
        assert Name("hammer").value == "hammer"

    def test_strips_whitespace(self):
        assert Name("  hammer  ").value == "hammer"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            Name("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError, match="empty"):
            Name("   ")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="100"):
            Name("x" * 101)

    def test_is_frozen(self):
        with pytest.raises(AttributeError):
            Name("hammer").value = "other"


class TestDescription:
    def test_defaults_to_empty(self):
        assert Description().value == ""

    def test_strips_whitespace(self):
        assert Description("  a tool  ").value == "a tool"

    def test_allows_empty(self):
        assert Description("").value == ""

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="500"):
            Description("x" * 501)


class TestItem:
    def test_create_raises_item_created(self):
        item = Item.create(Name("hammer"), Description("a tool"))

        events = item.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, ItemCreated)
        assert event.item_id == item.id
        assert event.name == "hammer"
        assert event.description == "a tool"

    def test_direct_construction_does_not_emit_events(self):
        item = Item(name=Name("hammer"), description=Description("a tool"))
        assert item.collect_events() == []

    def test_update_name_raises_item_updated(self):
        item = Item.create(Name("hammer"), Description("a tool"))
        item.collect_events()

        item.update_name(Name("mallet"))

        events = item.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, ItemUpdated)
        assert event.item_id == item.id
        assert event.name == "mallet"
        assert event.description == "a tool"

    def test_update_description_raises_item_updated(self):
        item = Item.create(Name("hammer"), Description("a tool"))
        item.collect_events()

        item.update_description(Description("heavy tool"))

        events = item.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], ItemUpdated)
        assert events[0].description == "heavy tool"

    def test_collect_events_drains(self):
        item = Item.create(Name("hammer"), Description("a tool"))
        item.update_name(Name("mallet"))

        first = item.collect_events()
        second = item.collect_events()

        assert len(first) == 2
        assert second == []

    def test_identity_equality(self):
        a = Item(name=Name("hammer"), description=Description("x"))
        b = Item(name=Name("hammer"), description=Description("x"))

        assert a != b
        assert a == a

    def test_unique_ids(self):
        a = Item(name=Name("a"), description=Description(""))
        b = Item(name=Name("b"), description=Description(""))

        assert a.id != b.id
