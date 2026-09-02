"""Unit tests for the Items service layer, using in-memory adapters."""
import pytest

from items.adapters.unit_of_work import InMemoryUnitOfWork
from items.domain.exceptions import ItemNotFoundError
from items.service_layer.commands import CreateItem, DeleteItem, UpdateItem
from items.service_layer.handlers import ItemCommandHandlers, ItemQueryHandlers
from items.service_layer.queries import GetItem, ListItems


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def commands(uow):
    return ItemCommandHandlers(uow)


@pytest.fixture
def queries(uow):
    return ItemQueryHandlers(uow)


def _create(commands, name="hammer", description="a tool"):
    return commands.handle_create(CreateItem(name=name, description=description))


class TestCreateItem:
    def test_adds_item_to_repository(self, commands, queries):
        item = _create(commands)

        assert queries.handle_get(GetItem(item_id=item.id)) is item

    def test_emits_item_created_via_uow(self, commands, uow):
        item = _create(commands)

        events = uow.collect_events()
        assert [type(e).__name__ for e in events] == ["ItemCreated"]
        assert events[0].item_id == item.id


class TestUpdateItem:
    def test_updates_name(self, commands, queries):
        item = _create(commands)

        updated = commands.handle_update(UpdateItem(item_id=item.id, name="mallet"))

        assert queries.handle_get(GetItem(item_id=item.id)).name.value == "mallet"
        assert updated.name.value == "mallet"

    def test_updates_description(self, commands):
        item = _create(commands)

        updated = commands.handle_update(
            UpdateItem(item_id=item.id, description="heavy tool")
        )

        assert updated.description.value == "heavy tool"

    def test_no_partial_fields_untouched(self, commands):
        item = _create(commands, description="original")

        updated = commands.handle_update(UpdateItem(item_id=item.id, name="new"))

        assert updated.description.value == "original"

    def test_unknown_item_raises(self, commands):
        import uuid

        with pytest.raises(ItemNotFoundError):
            commands.handle_update(UpdateItem(item_id=uuid.uuid4(), name="x"))

    def test_emits_item_updated_via_uow(self, commands, uow):
        item = _create(commands)
        uow.collect_events()

        commands.handle_update(UpdateItem(item_id=item.id, name="mallet"))

        assert [type(e).__name__ for e in uow.collect_events()] == ["ItemUpdated"]


class TestDeleteItem:
    def test_deletes_existing_item(self, commands, queries):
        item = _create(commands)

        commands.handle_delete(DeleteItem(item_id=item.id))

        assert queries.handle_get(GetItem(item_id=item.id)) is None

    def test_unknown_item_raises(self, commands):
        import uuid

        with pytest.raises(ItemNotFoundError):
            commands.handle_delete(DeleteItem(item_id=uuid.uuid4()))


class TestQueries:
    def test_get_missing_returns_none(self, queries):
        import uuid

        assert queries.handle_get(GetItem(item_id=uuid.uuid4())) is None

    def test_list_returns_all_items(self, commands, queries):
        first = _create(commands, name="a")
        second = _create(commands, name="b")

        items = queries.handle_list(ListItems())

        assert {item.id for item in items} == {first.id, second.id}


class TestSeenTracking:
    def test_collect_events_only_covers_touched_aggregates(self, commands, uow):
        first = _create(commands, name="first")
        uow.collect_events()

        second = _create(commands, name="second")

        events = uow.collect_events()
        assert len(events) == 1
        assert events[0].item_id == second.id

    def test_seen_is_empty_after_collection(self, commands, uow):
        _create(commands)
        uow.collect_events()

        assert uow.seen == set()

    def test_query_does_not_mark_aggregates_seen(self, commands, queries, uow):
        item = _create(commands)
        uow.collect_events()

        queries.handle_list(ListItems())

        assert uow.seen == set()
