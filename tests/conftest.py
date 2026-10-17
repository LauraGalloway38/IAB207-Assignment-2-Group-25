
import pytest

from nightbite import create_app, db


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "nightbite_test.sqlite"

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "nightbite-test-only-secret",
    })

    with app.app_context():
        db.create_all()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
