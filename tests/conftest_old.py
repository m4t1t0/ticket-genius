"""Pytest configuration for tests using test database."""
import os
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from items.adapters import orm


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables."""
    load_dotenv(".env.test")


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    url = os.environ["DATABASE_URL"]
    engine = create_engine(url)
    orm.start_mappers()
    orm.metadata.create_all(engine)
    yield engine
    orm.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    """Provide a transactional session for a test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()

    yield session

    session.close()
    # Transaction is closed by session.close(), no need to rollback
    connection.close()


@pytest.fixture
def client(db_session, monkeypatch):
    """Test client with test database."""
    from app import create_app

    def mock_build_uow(database_url=None):
        from items.adapters.unit_of_work import SqlAlchemyUnitOfWork
        return SqlAlchemyUnitOfWork(lambda: db_session)

    monkeypatch.setattr("items.entrypoints.bootstrap.build_uow", mock_build_uow)

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client