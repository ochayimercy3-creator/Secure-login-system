# Secure Login System (online mobile web app)

This project is a mobile-friendly Flask application that can be hosted online and accessed by multiple people. Once hosted on HTTPS, users can install it from Chrome using **Add to Home screen** / **Install app**.

## Features
- User registration and login
- Password hashing
- Email OTP verification (5-minute expiry)
- Five failed-password attempts trigger a 15-minute lock
- Admin login, user enable/disable, and recent activity logs
- Dedicated Login Successful page; no general-user dashboard
- Responsive design and basic PWA support

## Deploy online
1. Create a GitHub account and upload the contents of this folder to a new repository.
2. Create a web service on Render and connect that repository. Render can use `render.yaml`.
3. In the service environment settings, set `ADMIN_EMAIL` and a strong unique `ADMIN_PASSWORD`.
4. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` so OTPs are emailed. Do not leave SMTP unconfigured for public use.
5. Deploy. Open the HTTPS URL provided by the host.

## Install on Android
Open the deployed HTTPS URL in Chrome, tap the three-dot menu, then **Install app** or **Add to Home screen**.

## Important production notes
- Set a long random `SECRET_KEY` in the host environment.
- Use a persistent disk or managed database for production persistence. The starter uses SQLite; ephemeral hosting files may be reset during redeploy/restart.
- Configure HTTPS, SMTP, backups, rate limiting, and a production database before real public use.
- Admin credentials must be unique and never shared with ordinary users.
- The development OTP fallback prints codes in server logs only and is not suitable for a public deployment.
- This is a hosted web app/PWA, not a standalone APK. A public URL and hosting account are required for other people to access it.
