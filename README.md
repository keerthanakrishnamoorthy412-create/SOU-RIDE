# SOU Ride (RideSync) 🚗🎓
### Peer-to-Peer Campus Mobility & Carpooling Platform for Silver Oak University (Ahmedabad)

**SOU Ride** is an academic mobility platform developed specifically for the Silver Oak University community (Gota, Ahmedabad, Gujarat). It enables students, faculty, and campus staff to carpool, reduce commute costs, decrease traffic congestion along SG Highway, and travel safely through verified campus peer connections.

---

## 🌟 Key Features

1. **Institutional Verification & Multi-Tier Identity Trust**
   - **Direct Email Verification**: Instant verification for institutional `@silveroakuni.ac.in` university accounts.
   - **Photo ID Card Upload & Verification**: Designed for students and faculty without a university email (e.g. personal Gmail/Yahoo accounts). Users can upload their official Silver Oak University Student ID Card or Admission Fee Slip.
   - **Temporary 1st Semester Student Support**: Full support for temporary enrollment numbers starting with `T` (e.g., `T2501030600023`) assigned to new admissions or 1st semester students.
   - **Automated Authenticity Analysis**: PIL-based heuristic analysis verifies image file integrity, decodability, resolution (minimum 250×150), standard card aspect ratios (0.4–2.6), and grayscale variance (≥ 20) to detect and reject blank or fake placeholder images before admin triage.
   - **Distinct Community Trust Badges**:
     - `✓ Verified Temp (1st Sem)` (Purple chip) for verified temporary 1st-sem students.
     - `✓ Verified SOU Student` (Emerald green chip) for institutional email accounts.
     - `✓ Verified SOU ID Card` (Emerald green chip) for non-college email users verified via ID card.
     - `⏳ ID Card In Review` (Amber pill) for pending moderation queue.
     - `✕ Verification Rejected` (Red pill) with clear feedback for re-submission.
     - `Unverified Community` (Slate gray chip) for unverified personal accounts.

2. **Ride Sharing & Intelligent Discovery**
   - **Offer Rides**: Drivers can post available seats, pickup gates, vehicle details, fuel contribution amounts (or free carpools), AC availability, and gender preferences ("Women Only", "Open to All").
   - **Find Rides**: Instant filtering by pickup location, drop-off destination, date, and gender preferences.
   - **Interactive Route Map**: Leaflet.js map with major Ahmedabad commute landmarks (SOU Main Gate, Gota Chokdi, Vaishno Devi Circle, Chandkheda, Ranip, Vastrapur, Geeta Mandir, etc.).

3. **Robust Booking Lifecycle & Seat Integrity**
   - **Seat Reservation**: Passengers request seats with custom notes and pickup preferences.
   - **Driver Approvals**: Drivers review pending requests and approve/reject bookings.
   - **Atomic Seat Accounting**: Real-time decrement of available seats upon acceptance and instant seat restoration if a booking is cancelled.
   - **Completion & Feedback**: Seamless completion with a 5-star rating and review system.

4. **Campus Safety & Emergency SOS**
   - Integrated Gujarat emergency services quick-dial:
     - 🚨 **112**: All-in-one Police Emergency
     - 🛡️ **181**: Abhayam Women Helpline (Gujarat)
     - 🚑 **108**: Emergency Medical Ambulance
     - 🏢 **079-66046304**: Silver Oak University Security Desk (Gota Campus)
   - Built-in Incident Reporting system for unsafe driving, harassment, or fare disputes.

5. **Campus Moderation & Admin Dashboard**
   - **ID Verification Queue**: Inspect uploaded student ID card photos with interactive lightbox zoom.
   - **1-Click Approvals**: Grant verified student badge with automated in-app confirmation notification.
   - **Structured Rejection Presets**: Pre-configured rejection reasons (blurry photo, enrollment number mismatch, unreadable card) notifying students in real time so they can re-upload.
   - **Safety Incident Triage**: Full ticket lifecycle (Investigating, Resolved, Dismissed) with timestamps and reporter contact info.

6. **Student & Faculty Password Recovery**
   - **Forgot Password Workflow**: Seamless password reset accessible directly from the Sign In page.
   - **Cryptographic Token & 6-Digit OTP**: Generates self-expiring security tokens and randomized 6-digit verification codes for university and personal email accounts.
   - **Interactive Dispatch Confirmation**: Simulated campus email/SMS preview allowing instant 1-click reset or manual OTP code verification.

7. **Multi-Theme Customization Engine**
   - Instant theme switcher accessible from the topbar and public navbar:
     - 💜 **Royal SOU** (Default campus lavender & royal purple)
     - 🖤 **Clean Monochrome** (Uber & Apple style minimalist black & white)
     - ❤️ **Crimson Red** (Varsity campus red)
     - 💙 **Ocean Blue** (Electric navy & cyan)
     - 🌙 **Dark Mode** (Deep obsidian night commute mode)
   - Automatically saves and restores the user's preference in browser `localStorage`.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.14 / Flask 3.1
- **Database**: SQLite (local development) / PostgreSQL (production-ready configuration)
- **ORM**: Flask-SQLAlchemy 3.1
- **Forms & Validation**: Flask-WTF & WTForms (CSRF protection, enrollment format validation, phone validation)
- **Image Processing**: Pillow (PIL) for image integrity, resolution, aspect ratio, and contrast analysis
- **Security & Tokens**: itsdangerous cryptographic URLSafe serializer & Werkzeug password hashing
- **Frontend**: Semantic HTML5, Vanilla CSS3 (Multi-Theme CSS Variables, responsive glassmorphism), Leaflet.js
- **Testing**: Pytest (38 comprehensive unit & integration tests)

---

## 🚀 Getting Started

### 1. Installation
Clone or navigate to the project directory:
```bash
cd IDT_ANTIGRAVITY
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

### 2. Database Migration & Setup
Run the database migration to apply ID verification columns:
```bash
python migrate_db.py
```

### 3. Running the Server
```bash
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.

---

## 🧪 Running the Test Suite

Run the complete automated test suite:
```bash
python -m pytest -v
```

### Test Coverage Highlights (49 Tests):
- `tests/test_auth.py`: Registration, automatic university email verification, login with email, login with enrollment ID, login with phone number, password whitespace tolerance, and session management.
- `tests/test_id_verification.py`:
  - Image authenticity heuristic analysis (valid card, blank/solid color rejection, resolution check, aspect ratio check).
  - Temporary enrollment number support (`T2501030600023` detection and validation).
  - Photo ID card upload flow and transition to `pending` review.
  - Admin approval workflow granting `✓ Verified Temp (1st Sem)` or `✓ Verified SOU ID Card` badges.
  - Admin rejection workflow with reason explanation and re-upload capability.
  - Non-admin privilege enforcement on verification endpoints.
- `tests/test_rides.py`: Ride creation, destination searching, empty search handling, and public ride detail views.
- `tests/test_requests_lifecycle.py`: Complete end-to-end booking lifecycle, atomic seat deductions, cancellations with seat restoration, and post-ride reviews.
- `tests/test_security.py`: Self-booking prevention, duplicate request blocking, overcapacity safeguards, driver authorization checks, and admin role enforcement.
- `tests/test_password_reset.py`: Forgot password token issuance, OTP code verification, and account recovery.

---

## 🌐 Free Public Deployment (Render.com)

To get a permanent public URL (e.g. `https://sou-ride.onrender.com`):

1. **Push your code to GitHub** (follow the commands in the GitHub section below).
2. Sign in to [Render.com](https://render.com) using your GitHub account.
3. Click **New +** → **Web Service**.
4. Select your **`sou-ride`** GitHub repository.
5. Render will automatically detect `render.yaml` or you can enter:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
6. Click **Create Web Service**. Within 2 minutes, Render will deploy your application with a free **permanent public URL and automatic SSL/HTTPS**!

---

## 👥 Demo Accounts (1-Click Auto-Fill Available on Sign In Page)

| Role | Login Identifier (Email or Enrollment ID) | Password | Note / Status |
| :--- | :--- | :--- | :--- |
| **Campus Admin** | `admin@silveroakuni.ac.in` (or `FACULTY-SOU-001`) | `Admin@123` | Verified Campus Transport Admin |
| **Verified Student** | `2501030600029@silveroakuni.ac.in` (or `2501030600029`) | `Student@123` | ✓ Verified SOU Student (B.Tech) |
| **Fresh Registration** | Any personal or university email | Custom | Open for fresh student registration |

