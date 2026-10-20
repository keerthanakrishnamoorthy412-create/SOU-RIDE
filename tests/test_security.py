from models import db, Ride, RideRequest

def test_prevent_self_booking(auth_driver):
    # Driver (user_id=1) tries to request seat on own ride (driver_id=1)
    response = auth_driver.post("/ride/1/request", data={
        "seats_requested": 1
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"You cannot request a seat on your own ride" in response.data

def test_prevent_duplicate_request(auth_passenger, app):
    # First request
    auth_passenger.post("/ride/1/request", data={"seats_requested": 1}, follow_redirects=True)

    # Second request for same ride
    dup_resp = auth_passenger.post("/ride/1/request", data={"seats_requested": 1}, follow_redirects=True)
    assert dup_resp.status_code == 200
    assert b"You already have an active request" in dup_resp.data

def test_prevent_booking_full_or_cancelled_ride(auth_passenger, app):
    with app.app_context():
        ride = db.session.get(Ride, 1)
        ride.status = "Full"
        ride.seats = 0
        db_session = app.extensions["sqlalchemy"].session
        db_session.commit()

    resp = auth_passenger.post("/ride/1/request", data={"seats_requested": 1}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"This ride is no longer available or is completely full" in resp.data

def test_unauthorized_driver_action_rejected(auth_passenger, app):
    # Create request
    with app.app_context():
        req = RideRequest(ride_id=1, passenger_id=2, status="Pending", seats_requested=1)
        db_session = app.extensions["sqlalchemy"].session
        db_session.add(req)
        db_session.commit()
        req_id = req.id

    # Passenger (not driver of ride 1) attempts to accept request
    resp = auth_passenger.post(f"/requests/{req_id}/accept", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Unauthorized action" in resp.data

def test_admin_access_control(auth_passenger, auth_admin):
    # Regular student attempts to view /admin
    denied = auth_passenger.get("/admin", follow_redirects=True)
    assert b"Access denied. Admin privileges required" in denied.data

    # Admin user accesses /admin
    granted = auth_admin.get("/admin")
    assert granted.status_code == 200
    assert b"Campus Transit Moderation" in granted.data
