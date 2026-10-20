import pytest
from models import db, User, Notification
from werkzeug.security import check_password_hash
from app import generate_password_reset_token, verify_password_reset_token

def test_forgot_password_page_renders(client):
    """Test that the forgot password form loads successfully."""
    res = client.get("/forgot-password")
    assert res.status_code == 200
    assert b"Password Recovery" in res.data
    assert b"Registered Email Address" in res.data


def test_forgot_password_known_user_generates_token_and_otp(client, app):
    """Test requesting a password reset for a registered user."""
    res = client.post("/forgot-password", data={
        "email": "driver@silveroakuni.ac.in"
    })
    assert res.status_code == 200
    assert b"Password Reset Code Issued" in res.data
    assert b"6-Digit Security Verification Code" in res.data
    assert b"Proceed to Reset Password" in res.data

    with app.app_context():
        # Verify in-app notification dispatch
        user = User.query.filter_by(email="driver@silveroakuni.ac.in").first()
        notif = Notification.query.filter_by(user_id=user.id).order_by(Notification.id.desc()).first()
        assert notif is not None
        assert "Password Reset Requested" in notif.title


def test_forgot_password_unknown_email(client):
    """Test that requesting reset for an unknown email gracefully redirects without errors."""
    res = client.post("/forgot-password", data={
        "email": "nonexistent.user999@gmail.com"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"If that email address is registered" in res.data


def test_verify_reset_otp_flow(client, app):
    """Test entering the 6-digit OTP code to advance to the password reset form."""
    # First trigger forgot-password to set up session
    res = client.post("/forgot-password", data={
        "email": "driver@silveroakuni.ac.in"
    })
    assert res.status_code == 200

    with client.session_transaction() as sess:
        otp = sess.get("reset_otp")
        assert otp is not None
        assert len(otp) == 6

    # Submit the correct OTP code
    otp_res = client.post("/verify-reset-otp", data={
        "otp_code": otp
    }, follow_redirects=True)
    assert otp_res.status_code == 200
    assert b"Set New Password" in otp_res.data


def test_verify_reset_otp_invalid_code(client):
    """Test that an incorrect OTP code is rejected."""
    client.post("/forgot-password", data={
        "email": "driver@silveroakuni.ac.in"
    })

    bad_res = client.post("/verify-reset-otp", data={
        "otp_code": "000000"
    })
    assert bad_res.status_code == 200
    assert b"Incorrect verification code" in bad_res.data


def test_complete_password_reset_and_login_with_new_password(client, app):
    """Test setting a new password via the cryptographically signed link and logging in."""
    with app.app_context():
        token = generate_password_reset_token("driver@silveroakuni.ac.in")

    # Access reset form with valid token
    get_res = client.get(f"/reset-password/{token}")
    assert get_res.status_code == 200
    assert b"Set New Password" in get_res.data

    # Submit new password
    post_res = client.post(f"/reset-password/{token}", data={
        "password": "NewSecretPassword@2026",
        "confirm_password": "NewSecretPassword@2026"
    }, follow_redirects=True)

    assert post_res.status_code == 200
    assert b"Your password has been successfully reset!" in post_res.data

    # Verify password was updated in DB
    with app.app_context():
        user = User.query.filter_by(email="driver@silveroakuni.ac.in").first()
        assert check_password_hash(user.password, "NewSecretPassword@2026")

    # Now verify user can log in with the new password
    login_res = client.post("/login", data={
        "email": "driver@silveroakuni.ac.in",
        "password": "NewSecretPassword@2026"
    }, follow_redirects=True)

    assert login_res.status_code == 200
    assert b"Welcome back, Driver Keerthana!" in login_res.data


def test_reset_password_invalid_token(client):
    """Test that an invalid or tampered token is rejected."""
    res = client.get("/reset-password/tampered-or-expired-token", follow_redirects=True)
    assert res.status_code == 200
    assert b"invalid or has expired" in res.data


def test_instant_in_website_recovery_by_student_id(client, app):
    """Test recovering password directly inside the website using Student ID + Registered Phone."""
    res = client.post("/forgot-password", data={
        "form_type": "instant_recovery",
        "identifier": "2501030600029",
        "phone": "9876543210",
        "new_password": "InstantSuccessPass@123",
        "confirm_password": "InstantSuccessPass@123"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"has been reset" in res.data

    with app.app_context():
        user = User.query.filter_by(student_id="2501030600029").first()
        assert check_password_hash(user.password, "InstantSuccessPass@123")

    # Verify user can log in with new password
    login_res = client.post("/login", data={
        "email": "driver@silveroakuni.ac.in",
        "password": "InstantSuccessPass@123"
    }, follow_redirects=True)
    assert login_res.status_code == 200
    assert b"Welcome back, Driver Keerthana!" in login_res.data


def test_instant_in_website_recovery_by_email(client, app):
    """Test recovering password directly inside the website using personal email + Registered Phone."""
    res = client.post("/forgot-password", data={
        "form_type": "instant_recovery",
        "identifier": "kiran@gmail.com",
        "phone": "9123456780",
        "new_password": "PassengerNewPass@123",
        "confirm_password": "PassengerNewPass@123"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"has been reset" in res.data

    with app.app_context():
        user = User.query.filter_by(email="kiran@gmail.com").first()
        assert check_password_hash(user.password, "PassengerNewPass@123")


def test_instant_in_website_recovery_temporary_student(client, app):
    """Test recovering password for temporary 1st-sem student (T2501030600023)."""
    with app.app_context():
        temp_user = User(
            name="Rohan Temporary",
            email="rohan.temporary.test@gmail.com",
            password="oldpass123",
            student_id="T2501030600023",
            phone="9825123456",
            role="student"
        )
        db.session.add(temp_user)
        db.session.commit()

    res = client.post("/forgot-password", data={
        "form_type": "instant_recovery",
        "identifier": "T2501030600023",
        "phone": "9825123456",
        "new_password": "TempStudentPass@2026",
        "confirm_password": "TempStudentPass@2026"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"has been reset" in res.data

    with app.app_context():
        user = User.query.filter_by(student_id="T2501030600023").first()
        assert check_password_hash(user.password, "TempStudentPass@2026")


def test_instant_in_website_recovery_wrong_phone_rejected(client):
    """Test that mismatched phone number prevents unauthorized password resets."""
    res = client.post("/forgot-password", data={
        "form_type": "instant_recovery",
        "identifier": "2501030600029",
        "phone": "9999900000",
        "new_password": "HackerAttemptPass@123",
        "confirm_password": "HackerAttemptPass@123"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Phone verification failed" in res.data


def test_instant_in_website_recovery_unknown_identifier(client):
    """Test that an unknown student ID or email returns a clear error."""
    res = client.post("/forgot-password", data={
        "form_type": "instant_recovery",
        "identifier": "INVALID_ENROLLMENT_999",
        "phone": "9876543210",
        "new_password": "SomeNewPass@123",
        "confirm_password": "SomeNewPass@123"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"No registered student or faculty account found" in res.data

