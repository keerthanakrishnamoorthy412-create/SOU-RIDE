import os
import re
import uuid
import random
from datetime import datetime
from functools import wraps
from PIL import Image, ImageStat
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature

from models import db, User, Ride, RideRequest, Notification, Review, SafetyReport
from forms import (
    RegistrationForm, LoginForm, OfferRideForm, RequestRideForm,
    ProfileForm, SafetyReportForm, ReviewForm,
    IDCardVerificationForm, AdminRejectVerificationForm,
    ForgotPasswordForm, ResetPasswordForm, VerifyResetOTPForm,
    InstantAccountRecoveryForm
)

app = Flask(__name__)

# =========================================================
# CONFIGURATION
# =========================================================
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "sou_ride_2026_purple_key_dev")

# Upload Configuration for Student ID Card Verification
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads", "id_cards")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB maximum file size

# Database URI configuration: supports SQLite locally & PostgreSQL in deployment
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # Fix for Heroku/Render postgres:// prefix
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    db_file_path = os.path.abspath("database.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_file_path}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# CSRF Protection
csrf = CSRFProtect(app)

# Initialize Database
db.init_app(app)

with app.app_context():
    db.create_all()
    try:
        from seed import run_seed
        run_seed(app)
    except Exception as e:
        print(f"[Warning] Auto seed on init: {e}")


def analyze_id_card_photo(image_stream):
    """
    Heuristic authenticity & readability verification for SOU student ID cards:
    1. Verifies image decodability & integrity with PIL.
    2. Inspects resolution (minimum 250x150 pixels).
    3. Checks aspect ratio (between 0.4 and 2.6 to match standard portrait/landscape cards).
    4. Checks pixel variance to detect blank, solid colored, or fake images.
    """
    try:
        image_stream.seek(0)
        img = Image.open(image_stream)
        img.verify()

        image_stream.seek(0)
        img = Image.open(image_stream)
        img.load()

        width, height = img.size
        if width < 250 or height < 150:
            return False, f"Image resolution ({width}x{height}) is too low to clearly read student details (minimum 250x150 required)."

        aspect_ratio = width / height
        if aspect_ratio < 0.4 or aspect_ratio > 2.6:
            return False, f"Image proportions ({width}x{height}) do not match a standard ID card or admission slip format."

        # Variance check on grayscale values
        grayscale = img.convert("L")
        stat = ImageStat.Stat(grayscale)
        variance = stat.var[0]
        if variance < 20:
            return False, "Image appears blank, solid-colored, or lacks sufficient contrast to be a valid photo ID card."

        return True, f"Verified readable image ({img.format}, {width}x{height}, contrast variance {variance:.1f})"
    except Exception as e:
        return False, f"Invalid or unreadable image file: {str(e)}"



# =========================================================
# SECURITY & CONTEXT PROCESSORS
# =========================================================
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

@app.context_processor
def inject_globals():
    current_user = None
    unread_notifs = 0
    if "user_id" in session:
        current_user = db.session.get(User, session["user_id"])
        if current_user:
            unread_notifs = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()
        else:
            session.clear()
    return {
        "current_user": current_user,
        "unread_notifs": unread_notifs,
        "current_year": datetime.now().year,
        "ahmedabad_locations": [
            "Silver Oak University - Main Gate",
            "Silver Oak University - Block A",
            "Silver Oak University - Gate 2",
            "Gota Chokdi / Gota Cross Road",
            "Vaishno Devi Circle, SG Highway",
            "Chandkheda - Visat Circle",
            "Ranip - RTO Circle",
            "Vastrapur Lake / Alpha One",
            "Navrangpura - LD Engineering",
            "Geeta Mandir Bus Stand",
            "Kalupur Railway Station",
            "Gandhinagar - Infocity",
            "Bopal - South Bopal Circle",
            "Science City Road",
            "Memnagar - Helmet Circle"
        ]
    }

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in with an admin account.", "warning")
            return redirect(url_for("login", next=request.path))
        user = db.session.get(User, session["user_id"])
        if not user or not user.is_admin:
            flash("Access denied. Admin privileges required.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function

def notify_user(user_id, title, message, category="system", related_ride_id=None):
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        category=category,
        related_ride_id=related_ride_id,
        is_read=0,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.session.add(notif)


# =========================================================
# HOUSEKEEPING: AUTO-EXPIRE OUT-OF-DATE / PAST RIDES
# =========================================================
def cleanup_expired_rides():
    """
    Housekeeping utility: Automatically marks past/expired rides as 'Expired'.
    Checks both date and departure time against current local time.
    Cancels unfulfilled pending passenger requests with a polite notification.
    """
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    try:
        past_rides = Ride.query.filter(
            Ride.status.in_(["Available", "Full"]),
            (Ride.ride_date < current_date) |
            ((Ride.ride_date == current_date) & (Ride.ride_time < current_time))
        ).all()

        if past_rides:
            for r in past_rides:
                r.status = "Expired"
                for req in r.requests:
                    if req.status == "Pending":
                        req.status = "Expired"
                        req.updated_at = now.strftime("%Y-%m-%d %H:%M:%S")
                        notify_user(
                            req.passenger_id,
                            "Ride Expired",
                            f"The ride from {r.source} to {r.destination} on {r.ride_date} at {r.ride_time} has expired.",
                            category="booking",
                            related_ride_id=None
                        )
            db.session.commit()
            return len(past_rides)
    except Exception:
        db.session.rollback()
    return 0


# =========================================================
# HOME / LANDING PAGE
# =========================================================
@app.route("/")
def home():
    cleanup_expired_rides()
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    total_rides = Ride.query.count()
    active_rides = Ride.query.filter_by(status="Available").filter(Ride.seats > 0)\
        .filter((Ride.ride_date > current_date) | ((Ride.ride_date == current_date) & (Ride.ride_time >= current_time))).count()
    verified_users = User.query.filter_by(is_verified=1).count()
    completed_rides = Ride.query.filter_by(status="Completed").count()

    recent_rides = Ride.query.filter_by(status="Available").filter(Ride.seats > 0)\
        .filter((Ride.ride_date > current_date) | ((Ride.ride_date == current_date) & (Ride.ride_time >= current_time)))\
        .order_by(Ride.ride_date.asc(), Ride.ride_time.asc()).limit(4).all()

    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(3).all()

    return render_template(
        "index.html",
        total_rides=total_rides,
        active_rides=active_rides,
        verified_users=verified_users,
        completed_rides=completed_rides,
        recent_rides=recent_rides,
        recent_reviews=recent_reviews
    )


# =========================================================
# AUTHENTICATION
# =========================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    form = RegistrationForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if existing_user:
            flash("This email address is already registered. Please sign in.", "error")
            return render_template("register.html", form=form)

        email = form.email.data.strip().lower()
        is_verified = 1 if email.endswith("@silveroakuni.ac.in") else 0

        hashed_password = generate_password_hash(form.password.data)

        user = User(
            name=form.name.data.strip(),
            email=email,
            password=hashed_password,
            student_id=form.student_id.data.strip(),
            phone=form.phone.data.strip(),
            department=form.department.data,
            is_verified=is_verified,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        db.session.add(user)
        db.session.commit()

        notify_user(
            user.id,
            "Welcome to SOU Ride!",
            f"Hello {user.name}, your account has been created. {'Your Silver Oak University institutional email has been verified.' if is_verified else 'Verify your student enrollment ID in profile.'}",
            category="system"
        )
        db.session.commit()

        if is_verified:
            flash("Account created! Your @silveroakuni.ac.in email has been verified.", "success")
        else:
            flash("Account created! Please sign in with your credentials.", "success")

        return redirect(url_for("login"))

    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.email.data.strip()
        pwd = form.password.data

        # Normalize digits if identifier looks like a phone number
        phone_digits = re.sub(r"\D", "", identifier)
        if phone_digits.startswith("91") and len(phone_digits) == 12:
            phone_digits = phone_digits[2:]

        # Query user by Email (case-insensitive) OR Enrollment ID (case-insensitive)
        user = User.query.filter(
            (db.func.lower(User.email) == identifier.lower()) |
            (db.func.upper(User.student_id) == identifier.upper())
        ).first()

        # If not found and identifier contains phone digits, try matching by phone
        if not user and phone_digits and len(phone_digits) >= 10:
            user = User.query.filter(
                (User.phone == identifier) | (User.phone == phone_digits)
            ).first()

        # Check password against hashed password (testing both exact input and stripped input)
        if user and pwd and (check_password_hash(user.password, pwd) or check_password_hash(user.password, pwd.strip())):
            session["user_id"] = user.id
            session["user_name"] = user.name
            session.permanent = form.remember_me.data

            flash(f"Welcome back, {user.name}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page if next_page and next_page.startswith("/") else url_for("dashboard"))

        flash("Invalid email or password. Please try again.", "error")

    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("home"))


# =========================================================
# PASSWORD RECOVERY WORKFLOW (STUDENTS & FACULTY)
# =========================================================
def generate_password_reset_token(email):
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    return serializer.dumps(email, salt="sou-password-reset")

def verify_password_reset_token(token, max_age=1800):
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    try:
        email = serializer.loads(token, salt="sou-password-reset", max_age=max_age)
        return email
    except Exception:
        return None

def normalize_phone_digits(p):
    if not p:
        return ""
    digits = re.sub(r"\D", "", str(p))
    if digits.startswith("91") and len(digits) == 12:
        return digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        return digits[1:]
    return digits

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    instant_form = InstantAccountRecoveryForm()
    email_form = ForgotPasswordForm()

    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "instant_recovery" or "identifier" in request.form:
            if instant_form.validate_on_submit():
                identifier = instant_form.identifier.data.strip()
                phone_input = instant_form.phone.data.strip()
                new_pw = instant_form.new_password.data

                # Match either student_id (e.g. 2501030600029, T2501030600023) or email
                user = User.query.filter(
                    (User.email.ilike(identifier)) | (User.student_id.ilike(identifier))
                ).first()

                if user:
                    user_phone_clean = normalize_phone_digits(user.phone)
                    input_phone_clean = normalize_phone_digits(phone_input)

                    if user_phone_clean and user_phone_clean == input_phone_clean:
                        user.password = generate_password_hash(new_pw)
                        notify_user(
                            user.id,
                            "Password Reset Completed",
                            "Your SOU Ride account password was successfully reset directly on the campus portal.",
                            category="system"
                        )
                        db.session.commit()
                        flash(f"Success! Password for {user.name} ({user.student_id or user.email}) has been reset. Please sign in with your new password.", "success")
                        return redirect(url_for("login"))
                    else:
                        flash("Phone verification failed: The mobile number entered does not match our campus records for this student or faculty account.", "error")
                else:
                    flash("No registered student or faculty account found matching that Enrollment ID or email address.", "error")
            else:
                for field, errors in instant_form.errors.items():
                    for err in errors:
                        flash(f"{field.replace('_', ' ').title()}: {err}", "error")
        else:
            # Flow 2: Email OTP / Security Code Request
            if email_form.validate_on_submit():
                email = email_form.email.data.strip().lower()
                user = User.query.filter_by(email=email).first()

                if user:
                    token = generate_password_reset_token(user.email)
                    otp = f"{random.randint(100000, 999999)}"

                    session["reset_email"] = user.email
                    session["reset_user_id"] = user.id
                    session["reset_otp"] = otp
                    session["reset_token"] = token
                    session["reset_timestamp"] = datetime.now().timestamp()

                    notify_user(
                        user.id,
                        "Password Reset Requested",
                        f"A password reset request was initiated for your SOU account. Security OTP code: {otp}. Valid for 15 minutes.",
                        category="system"
                    )
                    db.session.commit()

                    reset_url = url_for("reset_password", token=token, _external=True)
                    return render_template(
                        "forgot_password_sent.html",
                        target_email=user.email,
                        demo_otp=otp,
                        reset_url=reset_url
                    )
                else:
                    flash("If that email address is registered with us, a password recovery code has been sent.", "info")
                    return redirect(url_for("login"))

    return render_template("forgot_password.html", instant_form=instant_form, email_form=email_form)


@app.route("/verify-reset-otp", methods=["POST"])
def verify_reset_otp():
    submitted_otp = request.form.get("otp_code", "").strip()
    session_otp = session.get("reset_otp")
    session_token = session.get("reset_token")
    session_time = session.get("reset_timestamp", 0)

    # 15 minutes = 900 seconds
    if not session_otp or (datetime.now().timestamp() - session_time > 900):
        flash("The verification code has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    if submitted_otp == session_otp and session_token:
        flash("Verification code confirmed! You can now choose your new password.", "success")
        return redirect(url_for("reset_password", token=session_token))

    flash("Incorrect verification code. Please check the code and try again.", "error")
    target_email = session.get("reset_email", "")
    reset_url = url_for("reset_password", token=session_token, _external=True) if session_token else ""
    return render_template(
        "forgot_password_sent.html",
        target_email=target_email,
        demo_otp=session_otp,
        reset_url=reset_url
    )


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    email = verify_password_reset_token(token)
    if not email:
        flash("The password reset link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found. Please try again.", "error")
        return redirect(url_for("forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password = generate_password_hash(form.password.data)
        db.session.commit()

        # Clear reset session markers
        session.pop("reset_email", None)
        session.pop("reset_user_id", None)
        session.pop("reset_otp", None)
        session.pop("reset_token", None)
        session.pop("reset_timestamp", None)

        notify_user(
            user.id,
            "Password Changed Successfully",
            "Your SOU Ride account password was recently updated. If you did not perform this change, contact campus security immediately.",
            category="system"
        )
        db.session.commit()

        flash("Your password has been successfully reset! Please sign in with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", form=form, reset_email=email)



# =========================================================
# DASHBOARD
# =========================================================
@app.route("/dashboard")
@login_required
def dashboard():
    cleanup_expired_rides()
    user = db.session.get(User, session["user_id"])
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    # Metrics
    my_rides_count = Ride.query.filter_by(driver_id=user.id).count()
    my_active_bookings_count = RideRequest.query.filter_by(passenger_id=user.id)\
        .filter(RideRequest.status.in_(["Pending", "Accepted"])).count()
    available_campus_rides_count = Ride.query.filter_by(status="Available")\
        .filter(Ride.seats > 0).filter(Ride.driver_id != user.id)\
        .filter((Ride.ride_date > current_date) | ((Ride.ride_date == current_date) & (Ride.ride_time >= current_time))).count()
    pending_driver_requests_count = RideRequest.query.join(Ride)\
        .filter(Ride.driver_id == user.id, RideRequest.status == "Pending").count()

    # Passenger bookings (recent 4)
    my_bookings = RideRequest.query.filter_by(passenger_id=user.id)\
        .order_by(RideRequest.id.desc()).limit(4).all()

    # Rides offered by current user (recent 4)
    my_rides = Ride.query.filter_by(driver_id=user.id)\
        .order_by(Ride.id.desc()).limit(4).all()

    # Upcoming available rides on campus (excluding user's own)
    available_rides = Ride.query.filter_by(status="Available")\
        .filter(Ride.seats > 0).filter(Ride.driver_id != user.id)\
        .filter((Ride.ride_date > current_date) | ((Ride.ride_date == current_date) & (Ride.ride_time >= current_time)))\
        .order_by(Ride.ride_date.asc(), Ride.ride_time.asc()).limit(6).all()

    return render_template(
        "dashboard.html",
        user=user,
        my_rides_count=my_rides_count,
        my_active_bookings_count=my_active_bookings_count,
        available_campus_rides_count=available_campus_rides_count,
        pending_driver_requests_count=pending_driver_requests_count,
        my_bookings=my_bookings,
        my_rides=my_rides,
        available_rides=available_rides
    )


# =========================================================
# FIND A RIDE (SEARCH)
# =========================================================
@app.route("/search", methods=["GET", "POST"])
def search():
    cleanup_expired_rides()
    user_id = session.get("user_id", 0)

    source = request.args.get("source", "").strip()
    destination = request.args.get("destination", "").strip()
    ride_date = request.args.get("ride_date", "").strip()
    gender_pref = request.args.get("gender_preference", "Any").strip()

    if request.method == "POST":
        source = request.form.get("source", "").strip()
        destination = request.form.get("destination", "").strip()
        ride_date = request.form.get("ride_date", "").strip()
        gender_pref = request.form.get("gender_preference", "Any").strip()

    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    # Base query: only active, upcoming rides
    query = Ride.query.filter_by(status="Available").filter(Ride.seats > 0)

    # Exclude past departure times
    if not ride_date:
        query = query.filter((Ride.ride_date > current_date) | ((Ride.ride_date == current_date) & (Ride.ride_time >= current_time)))
    elif ride_date == current_date:
        query = query.filter(Ride.ride_date == current_date).filter(Ride.ride_time >= current_time)
    else:
        query = query.filter(Ride.ride_date == ride_date)

    if user_id:
        query = query.filter(Ride.driver_id != user_id)

    if source:
        query = query.filter(Ride.source.ilike(f"%{source}%"))
    if destination:
        query = query.filter(Ride.destination.ilike(f"%{destination}%"))
    if gender_pref and gender_pref != "Any":
        query = query.filter(Ride.gender_preference.in_([gender_pref, "Any"]))

    rides = query.order_by(Ride.ride_date.asc(), Ride.ride_time.asc()).all()

    return render_template(
        "search_ride.html",
        rides=rides,
        source=source,
        destination=destination,
        ride_date=ride_date,
        gender_pref=gender_pref
    )


# =========================================================
# RIDE DETAIL
# =========================================================
@app.route("/ride/<int:ride_id>")
def ride_detail(ride_id):
    ride = Ride.query.get_or_444 if hasattr(Ride.query, "get_or_444") else Ride.query.get_or_404(ride_id)
    form = RequestRideForm()

    existing_request = None
    if "user_id" in session:
        existing_request = RideRequest.query.filter_by(
            ride_id=ride.id,
            passenger_id=session["user_id"]
        ).order_by(RideRequest.id.desc()).first()

    return render_template(
        "ride_detail.html",
        ride=ride,
        form=form,
        existing_request=existing_request
    )


# =========================================================
# OFFER A RIDE
# =========================================================
@app.route("/offer", methods=["GET", "POST"])
@login_required
def offer():
    form = OfferRideForm()

    if form.validate_on_submit():
        user = db.session.get(User, session["user_id"])

        ride = Ride(
            driver_id=user.id,
            source=form.source.data.strip(),
            destination=form.destination.data.strip(),
            ride_date=form.ride_date.data.strip(),
            ride_time=form.ride_time.data.strip(),
            seats=form.seats.data,
            total_seats=form.seats.data,
            price=form.price.data or 0.0,
            vehicle_model=form.vehicle_model.data.strip() if form.vehicle_model.data else "",
            vehicle_number=form.vehicle_number.data.strip() if form.vehicle_number.data else "",
            gender_preference=form.gender_preference.data,
            luggage_allowed=1 if form.luggage_allowed.data else 0,
            ac_available=1 if form.ac_available.data else 0,
            notes=form.notes.data.strip() if form.notes.data else "",
            status="Available",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        db.session.add(ride)
        db.session.commit()

        notify_user(
            user.id,
            "Ride Published",
            f"Your ride from {ride.source} to {ride.destination} on {ride.ride_date} at {ride.ride_time} is now live.",
            category="ride_update",
            related_ride_id=ride.id
        )
        db.session.commit()

        flash("Your ride has been successfully published for the SOU community!", "success")
        return redirect(url_for("my_rides"))

    return render_template("offer_ride.html", form=form)


# =========================================================
# REQUEST A RIDE (BOOKING)
# =========================================================
@app.route("/ride/<int:ride_id>/request", methods=["POST"])
@login_required
def request_ride(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    user_id = session["user_id"]

    # Prevent self-booking
    if ride.driver_id == user_id:
        flash("You cannot request a seat on your own ride.", "error")
        return redirect(url_for("ride_detail", ride_id=ride_id))

    # Check ride status
    if ride.status != "Available" or ride.seats <= 0:
        flash("This ride is no longer available or is completely full.", "error")
        return redirect(url_for("ride_detail", ride_id=ride_id))

    # Prevent duplicate active requests
    active_req = RideRequest.query.filter_by(ride_id=ride.id, passenger_id=user_id)\
        .filter(RideRequest.status.in_(["Pending", "Accepted"])).first()
    if active_req:
        flash(f"You already have an active request ({active_req.status}) for this ride.", "warning")
        return redirect(url_for("my_bookings"))

    seats_requested = int(request.form.get("seats_requested", 1))
    if seats_requested < 1 or seats_requested > ride.seats:
        flash(f"Invalid seat count requested. Only {ride.seats} seat(s) available.", "error")
        return redirect(url_for("ride_detail", ride_id=ride_id))

    pickup_location = request.form.get("pickup_location", "").strip()
    passenger_notes = request.form.get("passenger_notes", "").strip()

    req = RideRequest(
        ride_id=ride.id,
        passenger_id=user_id,
        status="Pending",
        seats_requested=seats_requested,
        pickup_location=pickup_location,
        passenger_notes=passenger_notes,
        requested_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.session.add(req)
    db.session.commit()

    # Notify driver
    passenger = db.session.get(User, user_id)
    notify_user(
        ride.driver_id,
        "New Ride Request",
        f"{passenger.name} has requested {seats_requested} seat(s) for your ride from {ride.source} to {ride.destination}.",
        category="booking",
        related_ride_id=ride.id
    )
    db.session.commit()

    flash("Ride request sent! You will be notified once the driver responds.", "success")
    return redirect(url_for("my_bookings"))


# =========================================================
# DRIVER REQUESTS MANAGEMENT
# =========================================================
@app.route("/requests")
@login_required
def requests_view():
    user_id = session["user_id"]
    status_filter = request.args.get("status", "All")

    query = RideRequest.query.join(Ride).filter(Ride.driver_id == user_id)

    if status_filter != "All":
        query = query.filter(RideRequest.status == status_filter)

    incoming_requests = query.order_by(RideRequest.id.desc()).all()

    return render_template(
        "requests.html",
        incoming_requests=incoming_requests,
        status_filter=status_filter
    )


@app.route("/requests/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(request_id):
    req = RideRequest.query.get_or_404(request_id)
    ride = req.ride
    user_id = session["user_id"]

    # Authorization
    if ride.driver_id != user_id:
        flash("Unauthorized action.", "error")
        return redirect(url_for("requests_view"))

    if req.status != "Pending":
        flash(f"Request cannot be accepted because it is already {req.status}.", "warning")
        return redirect(url_for("requests_view"))

    # Atomic seat check & decrement
    if ride.seats < req.seats_requested:
        flash("Not enough available seats left on this ride.", "error")
        return redirect(url_for("requests_view"))

    ride.seats -= req.seats_requested
    if ride.seats == 0:
        ride.status = "Full"

    req.status = "Accepted"
    req.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Notify passenger
    driver = db.session.get(User, user_id)
    notify_user(
        req.passenger_id,
        "Ride Request Accepted!",
        f"Your request for ride from {ride.source} to {ride.destination} has been ACCEPTED by {driver.name}. Contact: {driver.phone}.",
        category="booking",
        related_ride_id=ride.id
    )

    db.session.commit()
    flash(f"Request accepted! {req.passenger.name} has been confirmed for your ride.", "success")
    return redirect(url_for("requests_view"))


@app.route("/requests/<int:request_id>/reject", methods=["POST"])
@login_required
def reject_request(request_id):
    req = RideRequest.query.get_or_404(request_id)
    ride = req.ride
    user_id = session["user_id"]

    if ride.driver_id != user_id:
        flash("Unauthorized action.", "error")
        return redirect(url_for("requests_view"))

    if req.status != "Pending":
        flash(f"Request cannot be rejected because it is already {req.status}.", "warning")
        return redirect(url_for("requests_view"))

    req.status = "Rejected"
    req.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Notify passenger
    notify_user(
        req.passenger_id,
        "Ride Request Declined",
        f"Your request for ride from {ride.source} to {ride.destination} on {ride.ride_date} was declined by the driver.",
        category="booking",
        related_ride_id=ride.id
    )

    db.session.commit()
    flash("Ride request has been rejected.", "info")
    return redirect(url_for("requests_view"))


# =========================================================
# MY BOOKINGS (PASSENGER)
# =========================================================
@app.route("/my-bookings")
@login_required
def my_bookings():
    user_id = session["user_id"]
    bookings = RideRequest.query.filter_by(passenger_id=user_id)\
        .order_by(RideRequest.id.desc()).all()
    review_form = ReviewForm()

    return render_template(
        "my_bookings.html",
        bookings=bookings,
        review_form=review_form
    )


@app.route("/booking/<int:request_id>/cancel", methods=["POST"])
@login_required
def cancel_booking(request_id):
    req = RideRequest.query.get_or_404(request_id)
    user_id = session["user_id"]

    if req.passenger_id != user_id:
        flash("Unauthorized action.", "error")
        return redirect(url_for("my_bookings"))

    if req.status not in ["Pending", "Accepted"]:
        flash(f"Booking cannot be cancelled because it is already {req.status}.", "warning")
        return redirect(url_for("my_bookings"))

    ride = req.ride
    was_accepted = (req.status == "Accepted")

    # If booking was accepted, restore seat!
    if was_accepted:
        ride.seats += req.seats_requested
        if ride.status == "Full":
            ride.status = "Available"

        notify_user(
            ride.driver_id,
            "Booking Cancelled",
            f"{req.passenger.name} cancelled their accepted booking for your ride ({ride.source} -> {ride.destination}). {req.seats_requested} seat(s) restored.",
            category="booking",
            related_ride_id=ride.id
        )
    else:
        notify_user(
            ride.driver_id,
            "Request Cancelled",
            f"{req.passenger.name} cancelled their pending request for your ride.",
            category="booking",
            related_ride_id=ride.id
        )

    req.status = "Cancelled"
    req.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.session.commit()
    flash("Your booking has been cancelled safely. Any reserved seats were returned to the pool.", "info")
    return redirect(url_for("my_bookings"))


# =========================================================
# MY RIDES (DRIVER)
# =========================================================
@app.route("/my-rides")
@login_required
def my_rides():
    cleanup_expired_rides()
    user_id = session["user_id"]
    rides = Ride.query.filter_by(driver_id=user_id)\
        .order_by(Ride.id.desc()).all()

    active_rides = [r for r in rides if not r.is_expired and r.status in ["Available", "Full"]]
    past_rides = [r for r in rides if r.is_expired or r.status in ["Expired", "Completed", "Cancelled"]]

    return render_template(
        "my_rides.html",
        rides=rides,
        active_rides=active_rides,
        past_rides=past_rides
    )


@app.route("/ride/<int:ride_id>/cancel", methods=["POST"])
@login_required
def cancel_ride(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    user_id = session["user_id"]

    if ride.driver_id != user_id:
        flash("Unauthorized action.", "error")
        return redirect(url_for("my_rides"))

    if ride.status in ["Completed", "Cancelled"]:
        flash(f"Ride is already {ride.status}.", "warning")
        return redirect(url_for("my_rides"))

    ride.status = "Cancelled"

    # Cancel all pending and accepted requests and notify passengers
    for req in ride.requests:
        if req.status in ["Pending", "Accepted"]:
            req.status = "Cancelled"
            req.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            notify_user(
                req.passenger_id,
                "Ride Cancelled by Driver",
                f"The ride from {ride.source} to {ride.destination} on {ride.ride_date} at {ride.ride_time} was cancelled by the driver.",
                category="ride_update",
                related_ride_id=ride.id
            )

    db.session.commit()
    flash("Your ride has been cancelled. All passengers have been notified.", "info")
    return redirect(url_for("my_rides"))


@app.route("/ride/<int:ride_id>/delete", methods=["POST"])
@login_required
def delete_ride(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    user_id = session["user_id"]
    user = db.session.get(User, user_id)

    if ride.driver_id != user_id and not (user and user.is_admin):
        flash("Unauthorized action.", "error")
        return redirect(url_for("my_rides"))

    # Notify any accepted or pending passengers before deletion
    for req in ride.requests:
        if req.status in ["Pending", "Accepted"]:
            notify_user(
                req.passenger_id,
                "Ride Cancelled & Removed",
                f"The ride from {ride.source} to {ride.destination} scheduled for {ride.ride_date} at {ride.ride_time} was cancelled and deleted by the driver.",
                category="ride_update",
                related_ride_id=None
            )

    # Detach references from notifications and safety reports
    Notification.query.filter_by(related_ride_id=ride.id).update({Notification.related_ride_id: None})
    SafetyReport.query.filter_by(ride_id=ride.id).update({SafetyReport.ride_id: None})

    db.session.delete(ride)
    db.session.commit()
    flash("Ride has been permanently deleted from campus listings.", "success")
    return redirect(url_for("my_rides"))


@app.route("/my-rides/clear-expired", methods=["POST"])
@login_required
def clear_expired_rides():
    cleanup_expired_rides()
    user_id = session["user_id"]
    user_rides = Ride.query.filter_by(driver_id=user_id).all()
    to_delete = [r for r in user_rides if r.is_expired or r.status in ["Expired", "Completed", "Cancelled"]]

    count = len(to_delete)
    for r in to_delete:
        Notification.query.filter_by(related_ride_id=r.id).update({Notification.related_ride_id: None})
        SafetyReport.query.filter_by(ride_id=r.id).update({SafetyReport.ride_id: None})
        db.session.delete(r)

    if count > 0:
        db.session.commit()
        flash(f"Successfully cleaned up {count} past/expired ride(s) from your dashboard.", "success")
    else:
        flash("No expired or past rides found to clear.", "info")

    return redirect(url_for("my_rides"))


@app.route("/ride/<int:ride_id>/complete", methods=["POST"])
@login_required
def complete_ride(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    user_id = session["user_id"]

    if ride.driver_id != user_id:
        flash("Unauthorized action.", "error")
        return redirect(url_for("my_rides"))

    if ride.status in ["Completed", "Cancelled"]:
        flash(f"Ride is already {ride.status}.", "warning")
        return redirect(url_for("my_rides"))

    ride.status = "Completed"

    # Mark all accepted requests as completed and request feedback
    for req in ride.requests:
        if req.status == "Accepted":
            req.status = "Completed"
            req.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            notify_user(
                req.passenger_id,
                "Ride Completed! Rate Your Driver",
                f"Your ride from {ride.source} to {ride.destination} is marked completed. Share your rating in My Bookings!",
                category="booking",
                related_ride_id=ride.id
            )

    db.session.commit()
    flash("Ride marked completed! Passengers have been prompted to leave reviews.", "success")
    return redirect(url_for("my_rides"))


# =========================================================
# RATINGS & REVIEWS
# =========================================================
@app.route("/ride/<int:ride_id>/review", methods=["POST"])
@login_required
def submit_review(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    user_id = session["user_id"]

    # Verify user was an accepted passenger on this completed ride
    accepted_request = RideRequest.query.filter_by(ride_id=ride.id, passenger_id=user_id)\
        .filter(RideRequest.status.in_(["Accepted", "Completed"])).first()

    if not accepted_request and ride.driver_id != user_id:
        flash("Only confirmed passengers or drivers on this ride can submit a review.", "error")
        return redirect(url_for("my_bookings"))

    # Determine reviewee
    if user_id == ride.driver_id:
        target_passenger_id = request.form.get("target_user_id")
        reviewee_id = int(target_passenger_id) if target_passenger_id else 0
    else:
        reviewee_id = ride.driver_id

    # Check for duplicate review
    existing_review = Review.query.filter_by(
        ride_id=ride.id,
        reviewer_id=user_id,
        reviewee_id=reviewee_id
    ).first()

    if existing_review:
        flash("You have already submitted a review for this ride.", "warning")
        return redirect(url_for("my_bookings"))

    try:
        rating = int(request.form.get("rating", 5))
        rating = max(1, min(5, rating))
    except ValueError:
        rating = 5

    comment = request.form.get("comment", "").strip()

    review = Review(
        ride_id=ride.id,
        reviewer_id=user_id,
        reviewee_id=reviewee_id,
        rating=rating,
        comment=comment,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.session.add(review)

    # Notify reviewee
    reviewer = db.session.get(User, user_id)
    notify_user(
        reviewee_id,
        "New Review Received",
        f"{reviewer.name} left a {rating}-star rating for your completed ride.",
        category="system",
        related_ride_id=ride.id
    )

    db.session.commit()
    flash("Thank you for your rating and community feedback!", "success")
    return redirect(url_for("my_bookings"))


# =========================================================
# PROFILE & SETTINGS
# =========================================================
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = db.session.get(User, session["user_id"])
    form = ProfileForm(obj=user)
    id_form = IDCardVerificationForm(
        student_id=user.student_id,
        student_type="temporary" if user.is_temporary_student else "regular"
    )

    if form.validate_on_submit():
        user.name = form.name.data.strip()
        user.phone = form.phone.data.strip()
        user.department = form.department.data.strip() if form.department.data else user.department
        raw_id = form.student_id.data.strip().upper() if form.student_id.data else ""
        if raw_id:
            user.student_id = raw_id
            if raw_id.startswith("T"):
                user.student_type = "temporary"
        user.emergency_contact = form.emergency_contact.data.strip() if form.emergency_contact.data else ""
        user.bio = form.bio.data.strip() if form.bio.data else ""

        db.session.commit()
        session["user_name"] = user.name
        flash("Your profile details have been updated successfully.", "success")
        return redirect(url_for("profile"))

    reviews = Review.query.filter_by(reviewee_id=user.id)\
        .order_by(Review.created_at.desc()).all()

    return render_template(
        "profile.html",
        user=user,
        form=form,
        id_form=id_form,
        reviews=reviews
    )


@app.route("/profile/verify-id", methods=["POST"])
@login_required
def verify_id_card():
    user = db.session.get(User, session["user_id"])
    form = IDCardVerificationForm()

    if form.validate_on_submit():
        file = form.id_card_image.data
        if not file:
            flash("Please choose an ID card photo file to upload.", "error")
            return redirect(url_for("profile"))

        # Authenticity and readability verification with PIL
        is_valid_image, analysis_msg = analyze_id_card_photo(file.stream)
        if not is_valid_image:
            flash(f"ID Card Verification Failed: {analysis_msg}", "error")
            return redirect(url_for("profile"))

        # Parse enrollment number format (detects T-prefix for 1st sem temporary students)
        raw_enrollment = form.student_id.data.strip().upper()
        is_temp = raw_enrollment.startswith("T")
        student_type = "temporary" if is_temp else "regular"

        # Secure unique filename
        ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else "jpg"
        filename = f"id_{user.id}_{uuid.uuid4().hex[:10]}.{ext}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        file.stream.seek(0)
        file.save(filepath)

        user.student_id = raw_enrollment
        user.student_type = student_type
        user.id_card_image = filename
        user.id_verification_status = "pending"
        user.id_rejection_reason = ""
        user.id_submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        notify_user(
            user.id,
            "ID Card Submitted for Verification",
            f"Your SOU ID card photo ({raw_enrollment} - {'Temporary 1st Sem Student' if is_temp else 'Regular Student'}) passed image authenticity checks. The campus moderation team has queued it for review.",
            category="system"
        )
        db.session.commit()

        flash(
            f"ID Card uploaded successfully! Image authenticity checks passed ({'Temporary Student (T-Prefix detected)' if is_temp else 'Regular SOU Enrollment'}). Our campus moderation team has queued it for verification.",
            "success"
        )
        return redirect(url_for("profile"))

    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{field.replace('_', ' ').title()}: {error}", "error")
    return redirect(url_for("profile"))


# =========================================================
# IN-APP NOTIFICATIONS
# =========================================================
@app.route("/notifications")
@login_required
def notifications():
    user = db.session.get(User, session["user_id"])
    notifs = Notification.query.filter_by(user_id=user.id)\
        .order_by(Notification.id.desc()).all()

    return render_template("notifications.html", notifs=notifs)


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    user_id = session["user_id"]
    Notification.query.filter_by(user_id=user_id, is_read=0).update({"is_read": 1})
    db.session.commit()
    flash("All notifications marked as read.", "info")
    return redirect(url_for("notifications"))


# =========================================================
# SAFETY & EMERGENCY (PROTOTYPE DISCLOSURE)
# =========================================================
@app.route("/safety", methods=["GET", "POST"])
def safety():
    form = SafetyReportForm()

    if form.validate_on_submit():
        if "user_id" not in session:
            flash("Please log in to submit a safety incident report.", "warning")
            return redirect(url_for("login", next=url_for("safety")))

        report = SafetyReport(
            reporter_id=session["user_id"],
            category=form.category.data,
            details=form.details.data.strip(),
            status="Pending",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        db.session.add(report)
        db.session.commit()

        flash("Safety report submitted. The campus safety moderation team has been notified.", "success")
        return redirect(url_for("safety"))

    return render_template("safety.html", form=form)


# =========================================================
# ADMIN MODERATION AREA (PROTECTED)
# =========================================================
@app.route("/admin")
@admin_required
def admin():
    total_users = User.query.count()
    total_rides = Ride.query.count()
    total_requests = RideRequest.query.count()
    pending_reports = SafetyReport.query.filter_by(status="Pending").count()
    pending_id_verifications = User.query.filter_by(id_verification_status="pending").count()

    users = User.query.order_by(User.id.desc()).all()
    rides = Ride.query.order_by(Ride.id.desc()).all()
    reports = SafetyReport.query.order_by(SafetyReport.id.desc()).all()
    id_verification_users = User.query.filter(User.id_card_image != "").order_by(User.id.desc()).all()
    reject_form = AdminRejectVerificationForm()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_rides=total_rides,
        total_requests=total_requests,
        pending_reports=pending_reports,
        pending_id_verifications=pending_id_verifications,
        users=users,
        rides=rides,
        reports=reports,
        id_verification_users=id_verification_users,
        reject_form=reject_form
    )


@app.route("/admin/user/<int:user_id>/approve-id", methods=["POST"])
@admin_required
def admin_approve_id_verification(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    user.id_verification_status = "verified"
    user.is_verified = 1
    user.id_rejection_reason = ""
    db.session.commit()

    student_category_desc = "Temporary Student (1st Sem)" if user.is_temporary_student else "Student"
    notify_user(
        user.id,
        "ID Card Verification Approved! ✓",
        f"Congratulations {user.name}! Your Silver Oak University {student_category_desc} ID card ({user.student_id}) has been verified by Campus Moderation. Your verified community badge is now live.",
        category="system"
    )
    db.session.commit()

    flash(f"Verification approved for {user.name} ({user.student_id} - {student_category_desc}).", "success")
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/reject-id", methods=["POST"])
@admin_required
def admin_reject_id_verification(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    reason = request.form.get("rejection_reason", "").strip() or "ID card photo was unreadable or enrollment number did not match."
    user.id_verification_status = "rejected"
    user.id_rejection_reason = reason
    if not user.has_university_email:
        user.is_verified = 0
    db.session.commit()

    notify_user(
        user.id,
        "ID Card Verification Notice",
        f"Your ID card submission could not be verified. Reason: {reason}. You can re-upload a clear photo in your profile.",
        category="system"
    )
    db.session.commit()

    flash(f"ID Verification for {user.name} was rejected with reason: '{reason}'.", "info")
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/verify", methods=["POST"])
@admin_required
def admin_verify_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    user.is_verified = 0 if user.is_verified else 1
    if user.is_verified:
        user.id_verification_status = "verified"
    db.session.commit()

    notify_user(
        user.id,
        "Verification Status Updated",
        f"Your SOU Ride verification status was set to {'Verified' if user.is_verified else 'Unverified'} by Campus Moderation.",
        category="system"
    )
    db.session.commit()

    flash(f"Verification status for {user.name} updated to {'Verified' if user.is_verified else 'Unverified'}.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/report/<int:report_id>/status", methods=["POST"])
@admin_required
def admin_update_report_status(report_id):
    report = SafetyReport.query.get_or_404(report_id)
    new_status = request.form.get("status", "Investigating")
    admin_notes = request.form.get("admin_notes", "").strip()

    report.status = new_status
    if admin_notes:
        report.admin_notes = admin_notes

    db.session.commit()
    flash(f"Report #{report.id} updated to {new_status}.", "success")
    return redirect(url_for("admin"))


# =========================================================
# APPLICATION ENTRYPOINT
# =========================================================
if __name__ == "__main__":
    from migrate_db import migrate_database
    from seed import run_seed
    migrate_database()
    run_seed(app)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False if os.environ.get("PORT") else True)
