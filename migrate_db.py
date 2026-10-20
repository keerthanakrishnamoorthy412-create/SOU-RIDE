import sqlite3
import os

def migrate_database(db_path="database.db"):
    print(f"[*] Starting migration for {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Update USERS table columns
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]

    new_user_cols = {
        "role": "TEXT DEFAULT 'student'",
        "department": "TEXT DEFAULT 'Engineering & Technology'",
        "emergency_contact": "TEXT DEFAULT ''",
        "is_verified": "INTEGER DEFAULT 0",
        "bio": "TEXT DEFAULT ''",
        "id_card_image": "TEXT DEFAULT ''",
        "id_verification_status": "TEXT DEFAULT 'unverified'",
        "id_rejection_reason": "TEXT DEFAULT ''",
        "id_submitted_at": "TEXT DEFAULT ''",
        "student_type": "TEXT DEFAULT 'regular'"
    }
    for col, col_type in new_user_cols.items():
        if col not in user_cols:
            print(f"  + Adding column users.{col}")
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

    # Auto-verify existing silveroakuni.ac.in emails
    cursor.execute("""
        UPDATE users 
        SET is_verified = 1, id_verification_status = 'verified'
        WHERE email LIKE '%@silveroakuni.ac.in'
    """)

    # Mark temporary students whose enrollment starts with T
    cursor.execute("""
        UPDATE users
        SET student_type = 'temporary'
        WHERE student_id LIKE 'T%' OR student_id LIKE 't%'
    """)

    # Ensure admin role for demo admin if any or first student if specified
    # User 5 is an official university email: let's keep role student, or create a designated admin
    # 2. Update RIDES table columns
    cursor.execute("PRAGMA table_info(rides)")
    ride_cols = [row[1] for row in cursor.fetchall()]

    new_ride_cols = {
        "total_seats": "INTEGER DEFAULT 3",
        "price": "REAL DEFAULT 0.0",
        "vehicle_model": "TEXT DEFAULT ''",
        "vehicle_number": "TEXT DEFAULT ''",
        "gender_preference": "TEXT DEFAULT 'Any'",
        "luggage_allowed": "INTEGER DEFAULT 1",
        "ac_available": "INTEGER DEFAULT 1"
    }
    for col, col_type in new_ride_cols.items():
        if col not in ride_cols:
            print(f"  + Adding column rides.{col}")
            cursor.execute(f"ALTER TABLE rides ADD COLUMN {col} {col_type}")

    # Set total_seats = seats for any existing rides where total_seats is null or 0
    cursor.execute("UPDATE rides SET total_seats = seats WHERE total_seats IS NULL OR total_seats = 0")

    # 3. Update RIDE_REQUESTS table columns
    cursor.execute("PRAGMA table_info(ride_requests)")
    req_cols = [row[1] for row in cursor.fetchall()]

    new_req_cols = {
        "seats_requested": "INTEGER DEFAULT 1",
        "pickup_location": "TEXT DEFAULT ''",
        "passenger_notes": "TEXT DEFAULT ''",
        "updated_at": "TEXT DEFAULT ''"
    }
    for col, col_type in new_req_cols.items():
        if col not in req_cols:
            print(f"  + Adding column ride_requests.{col}")
            cursor.execute(f"ALTER TABLE ride_requests ADD COLUMN {col} {col_type}")

    # 4. Create NOTIFICATIONS table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT DEFAULT 'system',
            related_ride_id INTEGER,
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(related_ride_id) REFERENCES rides(id) ON DELETE SET NULL
        )
    """)

    # 5. Create REVIEWS table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ride_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            reviewee_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(ride_id) REFERENCES rides(id) ON DELETE CASCADE,
            FOREIGN KEY(reviewer_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(reviewee_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # 6. Create SAFETY_REPORTS table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS safety_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER NOT NULL,
            reported_user_id INTEGER,
            ride_id INTEGER,
            category TEXT NOT NULL,
            details TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            admin_notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(reporter_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(reported_user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY(ride_id) REFERENCES rides(id) ON DELETE SET NULL
        )
    """)

    # 7. Create helpful indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rides_driver ON rides(driver_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rides_search ON rides(source, destination, ride_date, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_ride ON ride_requests(ride_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_passenger ON ride_requests(passenger_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_reviewee ON reviews(reviewee_id)")

    conn.commit()
    conn.close()
    print("[OK] Migration completed successfully.")

if __name__ == "__main__":
    migrate_database()
