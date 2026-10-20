from models import User

def test_register_student_university_email(client, app):
    response = client.post("/register", data={
        "name": "New Student",
        "email": "student2026@silveroakuni.ac.in",
        "student_id": "2501030609999",
        "department": "Silver Oak College of Engineering & Technology",
        "phone": "9876543211",
        "password": "Password@123",
        "confirm_password": "Password@123"
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="student2026@silveroakuni.ac.in").first()
        assert user is not None
        assert user.is_verified == 1  # Auto-verified university email!
        assert user.password != "Password@123"  # Password was hashed!

def test_register_personal_email_unverified(client, app):
    response = client.post("/register", data={
        "name": "External Student",
        "email": "personal@gmail.com",
        "student_id": "2501030608888",
        "department": "Other",
        "phone": "9876543212",
        "password": "Password@123",
        "confirm_password": "Password@123"
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="personal@gmail.com").first()
        assert user is not None
        assert user.is_verified == 0  # Unverified personal email

def test_login_success(client):
    response = client.post("/login", data={
        "email": "driver@silveroakuni.ac.in",
        "password": "password123"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Welcome back, Driver Keerthana" in response.data

def test_login_invalid_password(client):
    response = client.post("/login", data={
        "email": "driver@silveroakuni.ac.in",
        "password": "wrongpassword"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data

def test_logout(auth_driver):
    response = auth_driver.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been signed out safely" in response.data

def test_protected_route_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
