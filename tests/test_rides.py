from datetime import datetime, timedelta
from models import db, Ride

def test_offer_ride_success(auth_driver, app):
    future_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    response = auth_driver.post("/offer", data={
        "source": "Silver Oak University - Block A",
        "destination": "Geeta Mandir Bus Stand",
        "ride_date": future_date,
        "ride_time": "18:00",
        "seats": 4,
        "price": 30.0,
        "vehicle_model": "Maruti Swift",
        "vehicle_number": "GJ-01-AB-1234",
        "gender_preference": "Any",
        "luggage_allowed": "y",
        "ac_available": "y",
        "notes": "Main gate pickup"
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        ride = Ride.query.filter_by(source="Silver Oak University - Block A").first()
        assert ride is not None
        assert ride.seats == 4
        assert ride.total_seats == 4
        assert ride.status == "Available"
        assert ride.driver_id == 1

def test_search_rides_by_destination(client):
    response = client.get("/search?destination=Vaishno+Devi")
    assert response.status_code == 200
    assert b"Vaishno Devi Circle" in response.data

def test_search_rides_no_match(client):
    response = client.get("/search?destination=NonExistentPlace")
    assert response.status_code == 200
    assert b"No matching rides found" in response.data

def test_ride_detail_view(client):
    response = client.get("/ride/1")
    assert response.status_code == 200
    assert b"Silver Oak University - Main Gate" in response.data
    assert b"Vaishno Devi Circle" in response.data
    assert b"Reserve Your Seat" in response.data

def test_delete_ride_by_driver(auth_driver, app):
    # Driver deletes their ride (id=1)
    response = auth_driver.post("/ride/1/delete", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        ride = db.session.get(Ride, 1)
        assert ride is None

def test_delete_ride_unauthorized(client, app):
    # Unauthenticated user cannot delete ride
    response = client.post("/ride/1/delete", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        ride = db.session.get(Ride, 1)
        assert ride is not None

def test_auto_expire_and_clear_expired(auth_driver, app):
    past_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    with app.app_context():
        past_ride = Ride(
            driver_id=1,
            source="Silver Oak University - Gate 2",
            destination="Kalupur Railway Station",
            ride_date=past_date,
            ride_time="10:00",
            seats=2,
            total_seats=2,
            price=25.0,
            status="Available"
        )
        db.session.add(past_ride)
        db.session.commit()
        past_ride_id = past_ride.id

    # Visiting /my-rides triggers cleanup_expired_rides
    response = auth_driver.get("/my-rides")
    assert response.status_code == 200
    with app.app_context():
        ride = db.session.get(Ride, past_ride_id)
        assert ride.status == "Expired"
        assert ride.is_expired is True

    # Driver clicks "Clear All Expired"
    response = auth_driver.post("/my-rides/clear-expired", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        ride = db.session.get(Ride, past_ride_id)
        assert ride is None
