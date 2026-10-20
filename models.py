from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    student_id = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), default="student")  # 'student', 'faculty', 'admin'
    department = db.Column(db.String(120), default="Engineering & Technology")
    emergency_contact = db.Column(db.String(20), default="")
    is_verified = db.Column(db.Integer, default=0)
    bio = db.Column(db.Text, default="")
    id_card_image = db.Column(db.String(255), default="")
    id_verification_status = db.Column(db.String(30), default="unverified")  # 'unverified', 'pending', 'verified', 'rejected'
    id_rejection_reason = db.Column(db.Text, default="")
    id_submitted_at = db.Column(db.String(30), default="")
    student_type = db.Column(db.String(30), default="regular")  # 'regular', 'temporary', 'faculty'
    created_at = db.Column(db.String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    rides_offered = db.relationship("Ride", backref="driver", foreign_keys="Ride.driver_id", lazy=True, cascade="all, delete-orphan")
    ride_requests = db.relationship("RideRequest", backref="passenger", foreign_keys="RideRequest.passenger_id", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy=True, cascade="all, delete-orphan")
    reviews_given = db.relationship("Review", backref="reviewer", foreign_keys="Review.reviewer_id", lazy=True)
    reviews_received = db.relationship("Review", backref="reviewee", foreign_keys="Review.reviewee_id", lazy=True)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def has_university_email(self):
        return self.email.lower().endswith("@silveroakuni.ac.in")

    @property
    def is_temporary_student(self):
        if not self.student_id:
            return False
        return self.student_id.strip().upper().startswith("T")

    @property
    def verification_badge_label(self):
        if self.is_verified:
            if self.is_temporary_student:
                return "✓ Verified Temp (1st Sem)"
            elif self.has_university_email:
                return "✓ Verified SOU Student"
            else:
                return "✓ Verified SOU ID Card"
        elif self.id_verification_status == "pending":
            return "⏳ ID Card In Review"
        elif self.id_verification_status == "rejected":
            return "✕ Verification Rejected"
        return "Unverified Community"

    @property
    def verification_badge_class(self):
        if self.is_verified:
            if self.is_temporary_student:
                return "verified-chip temp-student"
            return "verified-chip"
        elif self.id_verification_status == "pending":
            return "status-pill status-pending"
        elif self.id_verification_status == "rejected":
            return "status-pill status-rejected"
        return "unverified-chip"

    @property
    def average_rating(self):
        if not self.reviews_received:
            return 5.0  # default start rating
        ratings = [r.rating for r in self.reviews_received]
        return round(sum(ratings) / len(ratings), 1)

    @property
    def review_count(self):
        return len(self.reviews_received)

    @property
    def unread_notification_count(self):
        return Notification.query.filter_by(user_id=self.id, is_read=0).count()


class Ride(db.Model):
    __tablename__ = "rides"

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    source = db.Column(db.String(150), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    ride_date = db.Column(db.String(20), nullable=False)
    ride_time = db.Column(db.String(20), nullable=False)
    seats = db.Column(db.Integer, nullable=False)  # remaining available seats
    total_seats = db.Column(db.Integer, default=3)
    price = db.Column(db.Float, default=0.0)
    vehicle_model = db.Column(db.String(100), default="")
    vehicle_number = db.Column(db.String(30), default="")
    gender_preference = db.Column(db.String(20), default="Any")  # 'Any', 'Women Only', 'Men Only'
    luggage_allowed = db.Column(db.Integer, default=1)
    ac_available = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="Available")  # 'Available', 'Full', 'Completed', 'Cancelled'
    created_at = db.Column(db.String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    requests = db.relationship("RideRequest", backref="ride", lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="ride", lazy=True, cascade="all, delete-orphan")

    @property
    def is_full(self):
        return self.seats <= 0 or self.status == "Full"

    @property
    def is_cancelled(self):
        return self.status == "Cancelled"

    @property
    def is_completed(self):
        return self.status == "Completed"

    @property
    def is_expired(self):
        if self.status == "Expired":
            return True
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        if self.ride_date < today_str:
            return True
        if self.ride_date == today_str and self.ride_time < time_str:
            return True
        return False

    @property
    def accepted_passengers(self):
        return [req.passenger for req in self.requests if req.status == "Accepted"]


class RideRequest(db.Model):
    __tablename__ = "ride_requests"

    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey("rides.id"), nullable=False)
    passenger_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default="Pending")  # 'Pending', 'Accepted', 'Rejected', 'Cancelled', 'Completed'
    seats_requested = db.Column(db.Integer, default=1)
    pickup_location = db.Column(db.String(150), default="")
    passenger_notes = db.Column(db.Text, default="")
    requested_at = db.Column(db.String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = db.Column(db.String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), default="system")  # 'booking', 'ride_update', 'safety', 'system'
    related_ride_id = db.Column(db.Integer, db.ForeignKey("rides.id", ondelete="SET NULL"), nullable=True)
    is_read = db.Column(db.Integer, default=0)
    created_at = db.Column(db.String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey("rides.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5
    comment = db.Column(db.Text, default="")
    created_at = db.Column(db.String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class SafetyReport(db.Model):
    __tablename__ = "safety_reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ride_id = db.Column(db.Integer, db.ForeignKey("rides.id", ondelete="SET NULL"), nullable=True)
    category = db.Column(db.String(50), nullable=False)  # 'Rash Driving', 'Harassment', 'Unsafe Vehicle', 'No Show', 'Other'
    details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="Pending")  # 'Pending', 'Investigating', 'Resolved', 'Dismissed'
    admin_notes = db.Column(db.Text, default="")
    created_at = db.Column(db.String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    reporter = db.relationship("User", foreign_keys=[reporter_id], backref="reports_filed")
    reported_user = db.relationship("User", foreign_keys=[reported_user_id], backref="reports_received")
    ride = db.relationship("Ride", foreign_keys=[ride_id], backref="safety_reports")
