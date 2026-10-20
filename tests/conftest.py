import pytest
import os
import tempfile
from werkzeug.security import generate_password_hash
from app import app as flask_app
from models import db, User, Ride, RideRequest

@pytest.fixture(scope="session")
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    original_uri = flask_app.config.get("SQLALCHEMY_DATABASE_URI")
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False  # Disabled for unit tests to simplify direct form submissions
    flask_app.config["SECRET_KEY"] = "test-secret-key-12345"

    flask_app.extensions.pop("sqlalchemy", None)
    db.init_app(flask_app)

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.engine.dispose()

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except OSError:
        pass
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = original_uri

@pytest.fixture(autouse=True)
def clean_db(app):
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Create Driver (id=1)
        driver = User(
            name="Driver Keerthana",
            email="driver@silveroakuni.ac.in",
            password=generate_password_hash("password123"),
            student_id="2501030600029",
            phone="9876543210",
            role="student",
            is_verified=1
        )
        # Create Passenger (id=2)
        passenger = User(
            name="Passenger Kiran",
            email="kiran@gmail.com",
            password=generate_password_hash("password123"),
            student_id="2501030600023",
            phone="9123456780",
            role="student",
            is_verified=0
        )
        # Create Admin (id=3)
        admin = User(
            name="Admin Officer",
            email="admin@silveroakuni.ac.in",
            password=generate_password_hash("Admin@123"),
            student_id="ADMIN001",
            phone="9999988888",
            role="admin",
            is_verified=1
        )

        db.session.add_all([driver, passenger, admin])
        db.session.commit()

        # Create a sample ride (id=1)
        ride = Ride(
            driver_id=driver.id,
            source="Silver Oak University - Main Gate",
            destination="Vaishno Devi Circle",
            ride_date="2026-10-15",
            ride_time="17:30",
            seats=3,
            total_seats=3,
            price=20.0,
            vehicle_model="Honda Activa 6G",
            status="Available"
        )
        db.session.add(ride)
        db.session.commit()

        yield

        db.session.rollback()
        db.session.remove()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_driver(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Driver Keerthana"
    return c

@pytest.fixture
def auth_passenger(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 2
        sess["user_name"] = "Passenger Kiran"
    return c

@pytest.fixture
def auth_admin(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 3
        sess["user_name"] = "Admin Officer"
    return c
