import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField, FloatField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Optional

from flask_wtf.file import FileField, FileAllowed, FileRequired

def validate_indian_phone(form, field):
    if field.data:
        cleaned = re.sub(r'[\s\-\+]', '', field.data)
        if cleaned.startswith('91') and len(cleaned) == 12:
            cleaned = cleaned[2:]
        if not re.match(r'^[6-9]\d{9}$', cleaned):
            raise ValidationError("Please enter a valid 10-digit Indian mobile number.")

def validate_sou_enrollment(form, field):
    if field.data:
        val = field.data.strip().upper()
        # Either standard SOU enrollment (e.g. 2501030600029) OR temporary (e.g. T2501030600023)
        if val.startswith('T'):
            digits_part = val[1:]
            if not digits_part.isdigit() or len(digits_part) < 6:
                raise ValidationError("Temporary enrollment number must start with 'T' followed by your digits (e.g., T2501030600023).")
        else:
            if not val.isdigit() or len(val) < 6:
                raise ValidationError("Enrollment number must be numeric (e.g. 2501030600029) or start with 'T' for temporary students (e.g. T2501030600023).")

class RegistrationForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email Address", validators=[DataRequired(), Email(), Length(max=120)])
    student_id = StringField("Student Enrollment ID", validators=[DataRequired(), Length(min=5, max=30), validate_sou_enrollment])
    department = SelectField("Department / Institute", choices=[
        ("Silver Oak College of Engineering & Technology", "SOCET - Engineering & Technology"),
        ("Aditya Silver Oak Institute of Technology", "ASOIT - Technology"),
        ("Silver Oak Institute of Computer Applications", "Computer Applications (BCA/MCA)"),
        ("Silver Oak Institute of Management", "Management (BBA/MBA)"),
        ("Silver Oak Institute of Science", "Science (B.Sc/M.Sc)"),
        ("Other", "Other Department / Faculty")
    ], default="Silver Oak College of Engineering & Technology")
    phone = StringField("Mobile Phone (WhatsApp)", validators=[DataRequired(), validate_indian_phone])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, message="Password must be at least 6 characters.")])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Create SOU Ride Account")

class LoginForm(FlaskForm):
    email = StringField("Email Address", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In to SOU Ride")

class OfferRideForm(FlaskForm):
    source = StringField("Pickup Location / Campus Gate", validators=[DataRequired(), Length(max=150)])
    destination = StringField("Drop-off Destination", validators=[DataRequired(), Length(max=150)])
    ride_date = StringField("Ride Date (YYYY-MM-DD)", validators=[DataRequired()])
    ride_time = StringField("Departure Time (HH:MM)", validators=[DataRequired()])
    seats = IntegerField("Available Seats", validators=[DataRequired(), NumberRange(min=1, max=6, message="Seats must be between 1 and 6.")])
    price = FloatField("Fuel Contribution per Seat (Rs. 0 for Free Carpool)", default=0.0, validators=[NumberRange(min=0, max=500)])
    vehicle_model = StringField("Vehicle Model (e.g. Activa 6G, Swift, i20)", validators=[Optional(), Length(max=100)])
    vehicle_number = StringField("Vehicle Registration (e.g. GJ-01-AB-1234)", validators=[Optional(), Length(max=30)])
    gender_preference = SelectField("Co-passenger Preference", choices=[
        ("Any", "Open to All Students"),
        ("Women Only", "Women Passengers Only"),
        ("Men Only", "Men Passengers Only")
    ], default="Any")
    luggage_allowed = BooleanField("Small Backpack / Bag Allowed", default=True)
    ac_available = BooleanField("Air Conditioning (Car)", default=True)
    notes = TextAreaField("Pickup Notes / Landmarks (e.g., Gate 2, near Apple Lab)", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Publish Ride")

class RequestRideForm(FlaskForm):
    seats_requested = IntegerField("Number of Seats", default=1, validators=[DataRequired(), NumberRange(min=1, max=4)])
    pickup_location = StringField("Your Preferred Pickup Point", validators=[Optional(), Length(max=150)])
    passenger_notes = TextAreaField("Note for the Driver", validators=[Optional(), Length(max=300)])
    submit = SubmitField("Send Booking Request")

class ProfileForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField("Phone Number", validators=[DataRequired(), validate_indian_phone])
    department = StringField("Department / Branch", validators=[Optional(), Length(max=120)])
    student_id = StringField("Student Enrollment ID", validators=[Optional(), Length(max=30)])
    emergency_contact = StringField("Emergency Contact Number", validators=[Optional(), validate_indian_phone])
    bio = TextAreaField("About Me / Commute Route", validators=[Optional(), Length(max=400)])
    submit = SubmitField("Update Profile")

class SafetyReportForm(FlaskForm):
    category = SelectField("Issue Category", choices=[
        ("Rash Driving", "Rash / Dangerous Driving"),
        ("Harassment", "Inappropriate Behavior / Harassment"),
        ("Unsafe Vehicle", "Unsafe Vehicle Condition"),
        ("No Show", "Driver / Passenger No-show without notice"),
        ("Overcharging", "Fare Dispute / Overcharging"),
        ("Other", "Other Incident")
    ], validators=[DataRequired()])
    details = TextAreaField("Detailed Description of Incident", validators=[DataRequired(), Length(min=10, max=1000)])
    submit = SubmitField("Submit Safety Report")

class ReviewForm(FlaskForm):
    rating = SelectField("Rating", choices=[
        ("5", "5 Stars - Excellent Commute"),
        ("4", "4 Stars - Great & On Time"),
        ("3", "3 Stars - Average"),
        ("2", "2 Stars - Needs Improvement"),
        ("1", "1 Star - Poor Experience")
    ], default="5", validators=[DataRequired()])
    comment = TextAreaField("Your Review / Feedback", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Submit Review")

class IDCardVerificationForm(FlaskForm):
    student_id = StringField("Enrollment Number", validators=[
        DataRequired(message="Please enter your enrollment number."),
        Length(min=5, max=30),
        validate_sou_enrollment
    ])
    student_type = SelectField("Student Enrollment Category", choices=[
        ("regular", "Regular Student Enrollment (e.g., 2501030600029)"),
        ("temporary", "1st Semester / Temporary Student (e.g., T2501030600023)")
    ], default="regular")
    id_card_image = FileField("Upload College ID Card / Admission Slip (Front Photo)", validators=[
        FileRequired(message="Please select an image file of your ID card."),
        FileAllowed(["jpg", "jpeg", "png", "webp"], "Only JPG, JPEG, PNG, and WebP images are allowed.")
    ])
    submit = SubmitField("Submit ID Card for Verification")

class AdminRejectVerificationForm(FlaskForm):
    rejection_reason = TextAreaField("Reason for Rejection", validators=[
        DataRequired(message="Please provide a reason so the student can rectify their submission."),
        Length(min=5, max=500)
    ])
    submit = SubmitField("Reject Submission")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Registered University or Personal Email", validators=[
        DataRequired(message="Please enter your email address."),
        Email(message="Please enter a valid email address.")
    ])
    submit = SubmitField("Send Password Reset Code & Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[
        DataRequired(message="Please enter a new password."),
        Length(min=6, message="Password must be at least 6 characters.")
    ])
    confirm_password = PasswordField("Confirm New Password", validators=[
        DataRequired(message="Please confirm your new password."),
        EqualTo("password", message="Passwords must match.")
    ])
    submit = SubmitField("Update Password")


class VerifyResetOTPForm(FlaskForm):
    otp_code = StringField("6-Digit Verification Code", validators=[
        DataRequired(message="Please enter the 6-digit verification code."),
        Length(min=6, max=6, message="Verification code must be exactly 6 digits.")
    ])
    submit = SubmitField("Verify Code & Proceed")


class InstantAccountRecoveryForm(FlaskForm):
    identifier = StringField("Enrollment Number or Email", validators=[
        DataRequired(message="Please enter your enrollment number (e.g. 2501030600029 or T2501030600023) or registered email.")
    ])
    phone = StringField("Registered Mobile Number", validators=[
        DataRequired(message="Please enter your 10-digit registered mobile number.")
    ])
    new_password = PasswordField("New Password", validators=[
        DataRequired(message="Please enter a new password."),
        Length(min=6, message="Password must be at least 6 characters.")
    ])
    confirm_password = PasswordField("Confirm New Password", validators=[
        DataRequired(message="Please re-type your new password."),
        EqualTo("new_password", message="Passwords must match.")
    ])
    submit = SubmitField("Verify & Reset Password Instantly")



