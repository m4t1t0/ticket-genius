"""Tests for bootstrap wiring and event publishing."""
from items.entrypoints.bootstrap import bootstrap
from items.service_layer.commands import CreateItem, UpdateItem


def test_publisher_receives_events_after_commit(client):
    published = []
    bus = bootstrap(event_publisher=published.extend)

    item = bus.handle(CreateItem(name="hammer", description="a tool"))
    bus.handle(UpdateItem(item_id=item.id, name="mallet"))

    assert [type(e).__name__ for e in published] == ["ItemCreated", "ItemUpdated"]
    assert published[0].item_id == item.id
    assert published[1].name == "mallet"


def test_no_publisher_does_not_raise(client):
    bus = bootstrap()

    item = bus.handle(CreateItem(name="hammer", description="a tool"))

    assert item.name.value == "hammer"
