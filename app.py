import os, sqlite3, secrets, time, smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-deployment")
DB = os.environ.get("DATABASE_PATH", "secure_login.db")
SESSION_MINUTES = int(os.environ.get("SESSION_MINUTES", "20"))

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, active INTEGER DEFAULT 1,
            failed_attempts INTEGER DEFAULT 0, locked_until REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS otps(
            email TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY, email TEXT, event TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

def log(email, event):
    with db() as c:
        c.execute("INSERT INTO logs(email,event) VALUES(?,?)", (email, event))

def send_otp(email, code):
    host = os.environ.get("SMTP_HOST")
    if not host:
        # Local development only. Configure SMTP for a public deployment.
        print(f"DEVELOPMENT OTP for {email}: {code}")
        return
    msg = EmailMessage()
    msg["Subject"] = "Your Secure Login System verification code"
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = email
    msg.set_content(f"Your verification code is {code}. It expires in 5 minutes.")
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapped

@app.before_request
def set_session_lifetime():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=SESSION_MINUTES)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if len(password) < 10:
            flash("Use a password with at least 10 characters.")
        else:
            try:
                with db() as c:
                    c.execute("INSERT INTO users(email,password_hash) VALUES(?,?)",
                              (email, generate_password_hash(password)))
                log(email, "account_registered")
                flash("Account created. You can now log in.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        with db() as c:
            user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not user or not user["active"]:
                log(email, "login_rejected")
                flash("Invalid login details or account unavailable.")
            elif user["locked_until"] > time.time():
                flash("Account temporarily locked. Try again later.")
            elif check_password_hash(user["password_hash"], password):
                code = f"{secrets.randbelow(1000000):06d}"
                with db() as c2:
                    c2.execute("INSERT OR REPLACE INTO otps(email,code_hash,expires) VALUES(?,?,?)",
                               (email, generate_password_hash(code), time.time()+300))
                    c2.execute("UPDATE users SET failed_attempts=0 WHERE email=?", (email,))
                send_otp(email, code)
                session["pending_email"] = email
                log(email, "password_verified_otp_sent")
                return redirect(url_for("verify_otp"))
            else:
                attempts = user["failed_attempts"] + 1
                locked = time.time()+900 if attempts >= 5 else 0
                with db() as c2:
                    c2.execute("UPDATE users SET failed_attempts=?,locked_until=? WHERE email=?",
                               (attempts, locked, email))
                log(email, "failed_password")
                flash("Invalid login details or account unavailable.")
    return render_template("login.html")

@app.route("/verify-otp", methods=["GET","POST"])
def verify_otp():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("login"))
    if request.method == "POST":
        code = request.form.get("code","")
        with db() as c:
            otp = c.execute("SELECT * FROM otps WHERE email=?", (email,)).fetchone()
            if otp and otp["expires"] > time.time() and check_password_hash(otp["code_hash"], code):
                c.execute("DELETE FROM otps WHERE email=?", (email,))
                session.pop("pending_email", None)
                session["user_email"] = email
                session.permanent = True
                log(email, "login_success")
                return redirect(url_for("success"))
        log(email, "otp_failed")
        flash("The code is incorrect or expired. Please log in again.")
    return render_template("otp.html")

@app.route("/success")
def success():
    if not session.get("user_email"):
        return redirect(url_for("login"))
    return render_template("success.html", email=session["user_email"])

@app.route("/logout")
def logout():
    email = session.pop("user_email", None)
    if email: log(email, "logout")
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        email = os.environ.get("ADMIN_EMAIL","admin@example.com")
        password = os.environ.get("ADMIN_PASSWORD","ChangeThisAdminPassword!")
        if request.form.get("email","").strip().lower() == email.lower() and secrets.compare_digest(
            request.form.get("password",""), password):
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin"))
        flash("Incorrect administrator credentials.")
    return render_template("admin_login.html")

@app.route("/admin")
@admin_required
def admin():
    with db() as c:
        users = c.execute("SELECT id,email,active,created_at FROM users ORDER BY id DESC").fetchall()
        logs = c.execute("SELECT email,event,created_at FROM logs ORDER BY id DESC LIMIT 100").fetchall()
    return render_template("admin.html", users=users, logs=logs)

@app.route("/admin/toggle/<int:user_id>", methods=["POST"])
@admin_required
def toggle_user(user_id):
    with db() as c:
        c.execute("UPDATE users SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (user_id,))
    return redirect(url_for("admin"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
