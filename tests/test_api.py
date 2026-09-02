"""Integration tests for the Items HTTP API."""
import pytest


def _create_item(client, name="hammer", description="a tool"):
    response = client.post("/items", json={"name": name, "description": description})
    assert response.status_code == 201
    return response.get_json()


class TestCreate:
    def test_returns_201_with_payload(self, client):
        body = _create_item(client)

        assert body["name"] == "hammer"
        assert body["description"] == "a tool"
        assert body["id"]

    def test_missing_name_returns_400(self, client):
        response = client.post("/items", json={"description": "x"})

        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_empty_name_returns_400(self, client):
        response = client.post("/items", json={"name": "", "description": "x"})

        assert response.status_code == 400

    def test_too_long_name_returns_400(self, client):
        response = client.post("/items", json={"name": "x" * 101})

        assert response.status_code == 400

    def test_too_long_description_returns_400(self, client):
        response = client.post(
            "/items", json={"name": "ok", "description": "x" * 501}
        )

        assert response.status_code == 400

    def test_missing_body_returns_400(self, client):
        response = client.post("/items")

        assert response.status_code == 400


class TestRead:
    def test_get_existing_item(self, client):
        created = _create_item(client)

        response = client.get(f"/items/{created['id']}")

        assert response.status_code == 200
        assert response.get_json() == created

    def test_get_missing_item_returns_404(self, client):
        import uuid

        response = client.get(f"/items/{uuid.uuid4()}")

        assert response.status_code == 404

    def test_list_items(self, client):
        first = _create_item(client, name="a")
        second = _create_item(client, name="b")

        response = client.get("/items")

        ids = {item["id"] for item in response.get_json()}
        assert ids == {first["id"], second["id"]}


class TestUpdate:
    def test_update_returns_updated_payload(self, client):
        created = _create_item(client)

        response = client.put(
            f"/items/{created['id']}", json={"name": "mallet"}
        )

        assert response.status_code == 200
        body = response.get_json()
        assert body["name"] == "mallet"
        assert body["description"] == created["description"]

    def test_update_missing_returns_404(self, client):
        import uuid

        response = client.put(f"/items/{uuid.uuid4()}", json={"name": "x"})

        assert response.status_code == 404

    def test_invalid_name_returns_400_not_404(self, client):
        created = _create_item(client)

        response = client.put(
            f"/items/{created['id']}", json={"name": "x" * 101}
        )

        assert response.status_code == 400


class TestDelete:
    def test_delete_returns_204(self, client):
        created = _create_item(client)

        response = client.delete(f"/items/{created['id']}")

        assert response.status_code == 204
        assert client.get(f"/items/{created['id']}").status_code == 404

    def test_delete_missing_returns_404(self, client):
        import uuid

        response = client.delete(f"/items/{uuid.uuid4()}")

        assert response.status_code == 404
