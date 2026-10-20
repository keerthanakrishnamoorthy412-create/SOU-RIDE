from models import db, Ride, RideRequest, Notification, Review

def test_complete_booking_lifecycle_accept_and_seat_deduction(auth_passenger, auth_driver, app):
    # 1. Passenger requests 1 seat on ride 1 (initially 3 seats)
    req_resp = auth_passenger.post("/ride/1/request", data={
        "seats_requested": 1,
        "pickup_location": "Gate 1",
        "passenger_notes": "Leaving right after class"
    }, follow_redirects=True)
    assert req_resp.status_code == 200

    with app.app_context():
        req = RideRequest.query.filter_by(ride_id=1, passenger_id=2).first()
        assert req is not None
        assert req.status == "Pending"
        req_id = req.id

        # Driver should have received a notification
        driver_notif = Notification.query.filter_by(user_id=1, category="booking").first()
        assert driver_notif is not None
        assert "Passenger Kiran has requested" in driver_notif.message

    # 2. Driver accepts request
    accept_resp = auth_driver.post(f"/requests/{req_id}/accept", follow_redirects=True)
    assert accept_resp.status_code == 200

    with app.app_context():
        ride = db.session.get(Ride, 1)
        req = db.session.get(RideRequest, req_id)
        # Seat must be decremented from 3 to 2!
        assert ride.seats == 2
        assert req.status == "Accepted"

        # Passenger must have received notification
        p_notif = Notification.query.filter_by(user_id=2, category="booking").first()
        assert p_notif is not None
        assert "ACCEPTED" in p_notif.message

def test_passenger_cancel_accepted_booking_restores_seat(auth_passenger, auth_driver, app):
    # Setup accepted booking
    with app.app_context():
        ride = db.session.get(Ride, 1)
        ride.seats = 2
        req = RideRequest(
            ride_id=1,
            passenger_id=2,
            status="Accepted",
            seats_requested=1
        )
        db_session = app.extensions["sqlalchemy"].session
        db_session.add(req)
        db_session.commit()
        req_id = req.id

    # Passenger cancels booking
    cancel_resp = auth_passenger.post(f"/booking/{req_id}/cancel", follow_redirects=True)
    assert cancel_resp.status_code == 200

    with app.app_context():
        ride = db.session.get(Ride, 1)
        req = db.session.get(RideRequest, req_id)
        # SEAT MUST BE RESTORED from 2 to 3!
        assert ride.seats == 3
        assert req.status == "Cancelled"

        # Driver must be notified of cancellation and seat restoration
        driver_notif = Notification.query.filter_by(user_id=1, title="Booking Cancelled").first()
        assert driver_notif is not None
        assert "1 seat(s) restored" in driver_notif.message

def test_driver_reject_request_does_not_alter_seats(auth_passenger, auth_driver, app):
    with app.app_context():
        ride = db.session.get(Ride, 1)
        initial_seats = ride.seats
        req = RideRequest(
            ride_id=1,
            passenger_id=2,
            status="Pending",
            seats_requested=1
        )
        db_session = app.extensions["sqlalchemy"].session
        db_session.add(req)
        db_session.commit()
        req_id = req.id

    # Driver rejects
    reject_resp = auth_driver.post(f"/requests/{req_id}/reject", follow_redirects=True)
    assert reject_resp.status_code == 200

    with app.app_context():
        ride = db.session.get(Ride, 1)
        req = db.session.get(RideRequest, req_id)
        assert req.status == "Rejected"
        # Seats remain untouched
        assert ride.seats == initial_seats

def test_complete_ride_and_submit_review(auth_passenger, auth_driver, app):
    # Setup completed ride
    with app.app_context():
        ride = db.session.get(Ride, 1)
        req = RideRequest(
            ride_id=1,
            passenger_id=2,
            status="Accepted",
            seats_requested=1
        )
        db_session = app.extensions["sqlalchemy"].session
        db_session.add(req)
        db_session.commit()
        req_id = req.id

    # Driver marks completed
    complete_resp = auth_driver.post("/ride/1/complete", follow_redirects=True)
    assert complete_resp.status_code == 200

    with app.app_context():
        ride = db.session.get(Ride, 1)
        req = db.session.get(RideRequest, req_id)
        assert ride.status == "Completed"
        assert req.status == "Completed"

    # Passenger submits rating
    review_resp = auth_passenger.post("/ride/1/review", data={
        "rating": 5,
        "comment": "Punctual and very friendly student carpool!"
    }, follow_redirects=True)
    assert review_resp.status_code == 200

    with app.app_context():
        review = Review.query.filter_by(ride_id=1, reviewer_id=2).first()
        assert review is not None
        assert review.rating == 5
        assert review.reviewee_id == 1

