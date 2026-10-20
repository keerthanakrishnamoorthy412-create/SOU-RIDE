import io
import pytest
from PIL import Image, ImageDraw
import numpy as np
from models import db, User, Notification
from app import analyze_id_card_photo
from forms import RegistrationForm
from wtforms.validators import ValidationError

def create_test_image(width=500, height=320, solid_color=None):
    """Creates an in-memory JPEG byte stream for testing."""
    if solid_color:
        img = Image.new("RGB", (width, height), color=solid_color)
    else:
        # Create image with text/lines/rectangles to ensure high variance / realistic ID card look
        img = Image.new("RGB", (width, height), color=(240, 243, 246))
        draw = ImageDraw.Draw(img)
        # Header banner
        draw.rectangle([0, 0, width, 50], fill=(91, 33, 182))
        # Photo placeholder
        draw.rectangle([30, 70, 150, 220], fill=(160, 174, 192))
        # Text simulation lines
        draw.rectangle([170, 80, 450, 100], fill=(30, 41, 59))
        draw.rectangle([170, 115, 380, 130], fill=(71, 85, 105))
        draw.rectangle([170, 145, 420, 160], fill=(71, 85, 105))
        draw.rectangle([170, 175, 320, 190], fill=(148, 163, 184))
        # Barcode area
        for x in range(30, 470, 10):
            draw.line([(x, 260), (x, 295)], fill=(0, 0, 0), width=3)

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def test_analyze_id_card_photo_valid():
    """Verify that a standard-resolution card with variation passes authenticity check."""
    stream = create_test_image(width=500, height=320)
    valid, msg = analyze_id_card_photo(stream)
    assert valid is True
    assert "Verified readable image" in msg


def test_analyze_id_card_photo_blank_solid_rejected():
    """Verify that blank or solid-color uploads fail the variance check."""
    stream = create_test_image(width=500, height=320, solid_color=(255, 255, 255))
    valid, msg = analyze_id_card_photo(stream)
    assert valid is False
    assert "blank, solid-colored" in msg


def test_analyze_id_card_photo_low_resolution_rejected():
    """Verify that undersized images (<250x150) are rejected."""
    stream = create_test_image(width=180, height=100)
    valid, msg = analyze_id_card_photo(stream)
    assert valid is False
    assert "too low" in msg


def test_analyze_id_card_photo_bad_aspect_ratio_rejected():
    """Verify that extreme aspect ratio images (like banners or towers) are rejected."""
    # 900x300 has width >= 250, height >= 150, but aspect ratio is 3.0 (> 2.6)
    stream = create_test_image(width=900, height=300)
    valid, msg = analyze_id_card_photo(stream)
    assert valid is False
    assert "proportions" in msg


def test_temporary_student_registration(client, app):
    """Test registration with temporary 1st semester enrollment number starting with 'T'."""
    res = client.post("/register", data={
        "name": "Rohan Patel (1st Sem)",
        "email": "rohan.temp@gmail.com",
        "student_id": "T2501030600023",
        "department": "Silver Oak College of Engineering & Technology",
        "phone": "9825123456",
        "password": "Password@123",
        "confirm_password": "Password@123"
    }, follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="rohan.temp@gmail.com").first()
        assert user is not None
        assert user.student_id == "T2501030600023"
        assert user.is_temporary_student is True
        assert user.is_verified == 0
        assert user.verification_badge_label == "Unverified Community"


def test_enrollment_validation_rules(app):
    """Verify that validate_sou_enrollment accepts both regular and T-prefixed IDs."""
    from forms import validate_sou_enrollment

    class DummyField:
        def __init__(self, data):
            self.data = data

    class DummyForm:
        pass

    form = DummyForm()

    # Valid regular numeric enrollment
    validate_sou_enrollment(form, DummyField("2501030600029"))

    # Valid temporary enrollment with uppercase 'T'
    validate_sou_enrollment(form, DummyField("T2501030600023"))

    # Valid temporary enrollment with lowercase 't'
    validate_sou_enrollment(form, DummyField("t2501030600023"))

    # Invalid: non-numeric regular
    with pytest.raises(ValidationError):
        validate_sou_enrollment(form, DummyField("ABCDEFGHIJKL"))

    # Invalid: 'T' prefix with too few digits
    with pytest.raises(ValidationError):
        validate_sou_enrollment(form, DummyField("T123"))


def test_id_card_upload_success_temporary_student(auth_passenger, app):
    """Test uploading an authentic photo ID card for a temporary student."""
    img_buf = create_test_image(width=600, height=380)

    res = auth_passenger.post("/profile/verify-id", data={
        "student_id": "T2501030600023",
        "id_card_image": (img_buf, "my_sou_temp_id.jpg")
    }, content_type="multipart/form-data", follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        passenger = db.session.get(User, 2)
        assert passenger.student_id == "T2501030600023"
        assert passenger.student_type == "temporary"
        assert passenger.is_temporary_student is True
        assert passenger.id_verification_status == "pending"
        assert passenger.id_card_image is not None
        assert passenger.verification_badge_label == "⏳ ID Card In Review"
        assert passenger.verification_badge_class == "status-pill status-pending"


def test_id_card_upload_blank_image_fails_authenticity(auth_passenger, app):
    """Test that uploading a blank/fake image is caught by the authenticity filter."""
    blank_buf = create_test_image(width=500, height=320, solid_color=(255, 255, 255))

    res = auth_passenger.post("/profile/verify-id", data={
        "student_id": "T2501030600023",
        "id_card_image": (blank_buf, "blank_card.jpg")
    }, content_type="multipart/form-data", follow_redirects=True)

    assert res.status_code == 200
    assert b"ID Card Verification Failed" in res.data
    with app.app_context():
        passenger = db.session.get(User, 2)
        # Should not have transitioned to pending
        assert passenger.id_verification_status != "pending"


def test_admin_approve_temporary_student(auth_admin, app):
    """Test admin approving a temporary student's submitted ID card."""
    with app.app_context():
        passenger = db.session.get(User, 2)
        passenger.student_id = "T2501030600023"
        passenger.student_type = "temporary"
        passenger.id_verification_status = "pending"
        passenger.id_card_image = "test_temp_id.jpg"
        db.session.commit()

    # Admin approves
    res = auth_admin.post("/admin/user/2/approve-id", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        passenger = db.session.get(User, 2)
        assert passenger.is_verified == 1
        assert passenger.id_verification_status == "verified"
        assert passenger.verification_badge_label == "✓ Verified Temp (1st Sem)"
        assert passenger.verification_badge_class == "verified-chip temp-student"

        # Check in-app notification sent to passenger
        notif = Notification.query.filter_by(user_id=2).order_by(Notification.id.desc()).first()
        assert notif is not None
        assert "ID Card Verification Approved" in notif.title
        assert "T2501030600023" in notif.message


def test_admin_approve_regular_student_id_card(auth_admin, app):
    """Test admin approving a regular student without university email."""
    with app.app_context():
        passenger = db.session.get(User, 2)
        passenger.student_id = "2501030600088"
        passenger.student_type = "regular"
        passenger.id_verification_status = "pending"
        passenger.id_card_image = "regular_id.jpg"
        db.session.commit()

    res = auth_admin.post("/admin/user/2/approve-id", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        passenger = db.session.get(User, 2)
        assert passenger.is_verified == 1
        assert passenger.verification_badge_label == "✓ Verified SOU ID Card"
        assert passenger.verification_badge_class == "verified-chip"


def test_admin_reject_id_verification(auth_admin, app):
    """Test admin rejecting an ID card with a custom reason."""
    with app.app_context():
        passenger = db.session.get(User, 2)
        passenger.student_id = "T2501030600023"
        passenger.id_verification_status = "pending"
        passenger.id_card_image = "test_unclear.jpg"
        db.session.commit()

    reject_reason = "Photo is blurry and the enrollment number cannot be cross-referenced."
    res = auth_admin.post("/admin/user/2/reject-id", data={
        "rejection_reason": reject_reason
    }, follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        passenger = db.session.get(User, 2)
        assert passenger.id_verification_status == "rejected"
        assert passenger.id_rejection_reason == reject_reason
        assert passenger.verification_badge_label == "✕ Verification Rejected"
        assert passenger.verification_badge_class == "status-pill status-rejected"

        # Verify notification
        notif = Notification.query.filter_by(user_id=2).order_by(Notification.id.desc()).first()
        assert "ID Card Verification Notice" in notif.title
        assert reject_reason in notif.message


def test_non_admin_cannot_access_id_approval(auth_passenger, app):
    """Test that a regular student cannot approve or reject ID verifications."""
    res = auth_passenger.post("/admin/user/1/approve-id", follow_redirects=True)
    assert res.status_code == 200
    assert b"Access denied. Admin privileges required." in res.data
