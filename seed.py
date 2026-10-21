import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from flask import Flask
from models import db, User, Ride, RideRequest, Notification, Review

def run_seed(app):
    with app.app_context():
        print("[*] Running idempotent seed script...")

        # 1. Ensure Admin User
        admin_email = "admin@silveroakuni.ac.in"
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(
                name="SOU Campus Admin",
                email=admin_email,
                password=generate_password_hash("Admin@123"),
                student_id="FACULTY-SOU-001",
                phone="9876543210",
                role="admin",
                department="Campus Safety & Transport Cell",
                is_verified=1,
                bio="Official SOU Ride System Administrator & Campus Transit Coordinator.",
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            db.session.add(admin)
            db.session.commit()
            print(f"  + Created Admin user: {admin_email} (password: Admin@123)")
        else:
            admin.role = "admin"
            admin.is_verified = 1
            admin.password = generate_password_hash("Admin@123")
            db.session.commit()

        # 2. Ensure Verified Student Demo User (password: Student@123)
        student_email = "2501030600029@silveroakuni.ac.in"
        student = User.query.filter_by(email=student_email).first()
        if not student:
            student = User(
                name="Keerthana Chettiyar",
                email=student_email,
                password=generate_password_hash("Student@123"),
                student_id="2501030600029",
                phone="9876543210",
                role="student",
                department="Silver Oak College of Engineering & Technology",
                is_verified=1,
                bio="Silver Oak engineering student & regular campus carpooler.",
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            db.session.add(student)
            db.session.commit()
            print(f"  + Created Demo Student user: {student_email} (password: Student@123)")
        else:
            student.password = generate_password_hash("Student@123")
            student.is_verified = 1
            student.student_id = "2501030600029"
            student.phone = "9876543210"
            db.session.commit()
            print(f"  + Updated Demo Student user password to: Student@123")

        # 3. Synchronize all non-admin accounts to password Student@123 for seamless testing
        all_students = User.query.filter(User.role != "admin").all()
        for u in all_students:
            u.password = generate_password_hash("Student@123")
        db.session.commit()

        # 4. Check existing users and auto-verify silveroakuni.ac.in
        sou_users = User.query.filter(User.email.ilike("%@silveroakuni.ac.in")).all()
        for u in sou_users:
            u.is_verified = 1
        db.session.commit()

        # 5. Add realistic Ahmedabad university rides if fewer than 4 rides exist
        if Ride.query.count() < 4:
            today = datetime.now()
            sample_rides = [
                {
                    "driver_id": student.id,
                    "source": "Silver Oak University - Main Gate",
                    "destination": "Vaishno Devi Circle, SG Highway",
                    "ride_date": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "ride_time": "17:15",
                    "seats": 3,
                    "total_seats": 3,
                    "price": 0.0,
                    "vehicle_model": "Honda Activa 6G",
                    "vehicle_number": "GJ-01-ET-4521",
                    "gender_preference": "Any",
                    "notes": "Helmet mandatory. Leaving right after 5 PM lab session.",
                    "status": "Available"
                },
                {
                    "driver_id": admin.id,
                    "source": "Chandkheda - Visat Circle",
                    "destination": "Silver Oak University - Block A",
                    "ride_date": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "ride_time": "08:30",
                    "seats": 2,
                    "total_seats": 3,
                    "price": 20.0,
                    "vehicle_model": "Maruti Swift VXi",
                    "vehicle_number": "GJ-27-BC-8930",
                    "gender_preference": "Any",
                    "notes": "AC ride. Pickup near Visat circle BRTS bus stop.",
                    "status": "Available"
                },
                {
                    "driver_id": student.id,
                    "source": "Silver Oak University - Gate 2",
                    "destination": "Vastrapur Lake / Alpha One Mall",
                    "ride_date": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
                    "ride_time": "16:45",
                    "seats": 3,
                    "total_seats": 4,
                    "price": 30.0,
                    "vehicle_model": "Hyundai i20 Asta",
                    "vehicle_number": "GJ-01-KM-7712",
                    "gender_preference": "Any",
                    "notes": "Spacious car, boot space available for college bags.",
                    "status": "Available"
                },
                {
                    "driver_id": admin.id,
                    "source": "Gandhinagar - Infocity",
                    "destination": "Silver Oak University Campus",
                    "ride_date": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
                    "ride_time": "08:15",
                    "seats": 2,
                    "total_seats": 2,
                    "price": 0.0,
                    "vehicle_model": "Royal Enfield Classic 350",
                    "vehicle_number": "GJ-18-BQ-5519",
                    "gender_preference": "Any",
                    "notes": "Direct commute via SG Highway. Pickup at Infocity Circle.",
                    "status": "Available"
                }
            ]

            for r_data in sample_rides:
                r = Ride(
                    driver_id=r_data["driver_id"],
                    source=r_data["source"],
                    destination=r_data["destination"],
                    ride_date=r_data["ride_date"],
                    ride_time=r_data["ride_time"],
                    seats=r_data["seats"],
                    total_seats=r_data["total_seats"],
                    price=r_data["price"],
                    vehicle_model=r_data["vehicle_model"],
                    vehicle_number=r_data["vehicle_number"],
                    gender_preference=r_data["gender_preference"],
                    notes=r_data["notes"],
                    status=r_data["status"],
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                db.session.add(r)
            db.session.commit()
            print("  + Seeded realistic Silver Oak University Ahmedabad rides.")

        # 6. Add a sample review if none exist
        if Review.query.count() == 0 and Ride.query.first():
            ride1 = Ride.query.first()
            reviewer = admin if ride1.driver_id == student.id else student
            review = Review(
                ride_id=ride1.id,
                reviewer_id=reviewer.id,
                reviewee_id=ride1.driver_id,
                rating=5,
                comment="Super punctual and safe driver! Dropped right at campus on time. Highly recommended for daily SOU commutes.",
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            db.session.add(review)
            db.session.commit()
            print("  + Added sample review.")

        print("[OK] Seeding complete.")

def reset_database_fresh(app):
    with app.app_context():
        print("[*] Performing fresh database reset...")
        db.drop_all()
        db.create_all()
        run_seed(app)
        print("[OK] Database reset freshly completed.")

if __name__ == "__main__":
    from app import app
    run_seed(app)
