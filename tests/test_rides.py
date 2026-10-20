from models import Ride

def test_offer_ride_success(auth_driver, app):
    response = auth_driver.post("/offer", data={
        "source": "Silver Oak University - Block A",
        "destination": "Geeta Mandir Bus Stand",
        "ride_date": "2026-10-16",
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
