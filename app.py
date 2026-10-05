import os
import sqlite3
from datetime import date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "gym_management.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gym-management-dev-secret")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin'
    );

    CREATE TABLE IF NOT EXISTS members (
        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        age INTEGER,
        gender TEXT,
        join_date TEXT NOT NULL DEFAULT CURRENT_DATE
    );

    CREATE TABLE IF NOT EXISTS trainers (
        trainer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        specialization TEXT
    );

    CREATE TABLE IF NOT EXISTS membership_plans (
        plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_name TEXT NOT NULL UNIQUE,
        duration_months INTEGER NOT NULL CHECK(duration_months > 0),
        price REAL NOT NULL CHECK(price >= 0)
    );

    CREATE TABLE IF NOT EXISTS memberships (
        membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active',
        FOREIGN KEY(member_id) REFERENCES members(member_id) ON DELETE CASCADE,
        FOREIGN KEY(plan_id) REFERENCES membership_plans(plan_id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS attendance (
        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        attendance_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Present',
        UNIQUE(member_id, attendance_date),
        FOREIGN KEY(member_id) REFERENCES members(member_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK(amount >= 0),
        payment_date TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        FOREIGN KEY(member_id) REFERENCES members(member_id) ON DELETE CASCADE
    );
    """)

    # Safe first-run defaults. Existing data is preserved.
    db.execute(
        "INSERT OR IGNORE INTO users(username, password, role) VALUES (?, ?, ?)",
        ("admin", "admin123", "admin")
    )

    plans = [
        ("Monthly", 1, 1000),
        ("Quarterly", 3, 2700),
        ("Half-Yearly", 6, 5000),
        ("Yearly", 12, 9000),
    ]
    for plan in plans:
        db.execute(
            "INSERT OR IGNORE INTO membership_plans(plan_name, duration_months, price) VALUES (?, ?, ?)",
            plan,
        )
    db.commit()


@app.before_request
def prepare_request():
    init_db()
    if request.endpoint in {"login", "static"}:
        return
    if "user_id" not in session:
        return redirect(url_for("login"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        ).fetchone()
        if user:
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    db = get_db()
    stats = {
        "members": db.execute("SELECT COUNT(*) FROM members").fetchone()[0],
        "trainers": db.execute("SELECT COUNT(*) FROM trainers").fetchone()[0],
        "memberships": db.execute("SELECT COUNT(*) FROM memberships WHERE status = 'Active'").fetchone()[0],
        "payments": db.execute("SELECT COALESCE(SUM(amount), 0) FROM payments").fetchone()[0],
        "attendance_today": db.execute(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date = ? AND status = 'Present'",
            (date.today().isoformat(),),
        ).fetchone()[0],
    }
    return render_template("dashboard.html", stats=stats)


# Keep the old endpoint name used by some templates.
@app.route("/dashboard")
def dashboard_alias():
    return redirect(url_for("dashboard"))


@app.route("/members")
def members():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        rows = db.execute(
            """SELECT * FROM members
               WHERE name LIKE ? OR phone LIKE ? OR COALESCE(email,'') LIKE ?
               ORDER BY member_id DESC""",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM members ORDER BY member_id DESC").fetchall()
    return render_template("members.html", members=rows, q=q)


@app.route("/members/add", methods=["GET", "POST"])
def add_member():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        if not name or not phone:
            flash("Name and phone are required.", "error")
            return render_template("add_member.html")
        try:
            get_db().execute(
                """INSERT INTO members(name, phone, email, age, gender, join_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    name, phone,
                    request.form.get("email", "").strip() or None,
                    int(request.form["age"]) if request.form.get("age") else None,
                    request.form.get("gender") or None,
                    request.form.get("join_date") or date.today().isoformat(),
                ),
            )
            get_db().commit()
            flash("Member added successfully.", "success")
            return redirect(url_for("members"))
        except (ValueError, sqlite3.Error) as e:
            flash(f"Could not add member: {e}", "error")
    return render_template("add_member.html")


@app.route("/members/edit/<int:member_id>", methods=["GET", "POST"])
def edit_member(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)).fetchone()
    if not member:
        flash("Member not found.", "error")
        return redirect(url_for("members"))
    if request.method == "POST":
        try:
            db.execute(
                """UPDATE members SET name=?, phone=?, email=?, age=?, gender=?, join_date=?
                   WHERE member_id=?""",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("email", "").strip() or None,
                    int(request.form["age"]) if request.form.get("age") else None,
                    request.form.get("gender") or None,
                    request.form.get("join_date") or member["join_date"],
                    member_id,
                ),
            )
            db.commit()
            flash("Member updated successfully.", "success")
            return redirect(url_for("members"))
        except (ValueError, sqlite3.Error) as e:
            flash(f"Could not update member: {e}", "error")
    return render_template("edit_member.html", member=member)


@app.route("/members/delete/<int:member_id>", methods=["POST", "GET"])
def delete_member(member_id):
    db = get_db()
    db.execute("DELETE FROM members WHERE member_id = ?", (member_id,))
    db.commit()
    flash("Member deleted successfully.", "success")
    return redirect(url_for("members"))


@app.route("/attendance")
def attendance():
    db = get_db()
    rows = db.execute(
        """SELECT a.attendance_id, a.member_id, m.name, m.phone,
                  a.attendance_date, a.status
           FROM attendance a
           JOIN members m ON m.member_id = a.member_id
           ORDER BY a.attendance_date DESC, a.attendance_id DESC"""
    ).fetchall()
    return render_template("attendance.html", attendance=rows)


@app.route("/attendance/add", methods=["GET", "POST"])
def add_attendance():
    db = get_db()
    members_list = db.execute("SELECT member_id, name FROM members ORDER BY name").fetchall()
    if request.method == "POST":
        member_id = request.form.get("member_id")
        attendance_date = request.form.get("attendance_date") or date.today().isoformat()
        status = request.form.get("status", "Present")
        if not member_id:
            flash("Please select a member.", "error")
        else:
            try:
                db.execute(
                    """INSERT INTO attendance(member_id, attendance_date, status)
                       VALUES (?, ?, ?)
                       ON CONFLICT(member_id, attendance_date)
                       DO UPDATE SET status=excluded.status""",
                    (member_id, attendance_date, status),
                )
                db.commit()
                flash("Attendance saved successfully.", "success")
                return redirect(url_for("attendance"))
            except sqlite3.Error as e:
                flash(f"Could not save attendance: {e}", "error")
    return render_template("add_record.html", title="Add Attendance", members=members_list,
                           record_type="attendance", today=date.today().isoformat())


@app.route("/attendance/edit/<int:attendance_id>", methods=["GET", "POST"])
def edit_attendance(attendance_id):
    db = get_db()
    row = db.execute("SELECT * FROM attendance WHERE attendance_id = ?", (attendance_id,)).fetchone()
    if not row:
        flash("Attendance record not found.", "error")
        return redirect(url_for("attendance"))
    members_list = db.execute("SELECT member_id, name FROM members ORDER BY name").fetchall()
    if request.method == "POST":
        try:
            db.execute(
                """UPDATE attendance SET member_id=?, attendance_date=?, status=?
                   WHERE attendance_id=?""",
                (
                    request.form.get("member_id"),
                    request.form.get("attendance_date"),
                    request.form.get("status", "Present"),
                    attendance_id,
                ),
            )
            db.commit()
            flash("Attendance updated successfully.", "success")
            return redirect(url_for("attendance"))
        except sqlite3.Error as e:
            flash(f"Could not update attendance: {e}", "error")
    return render_template("edit_attendance.html", attendance=row, members=members_list)


@app.route("/attendance/delete/<int:attendance_id>", methods=["POST", "GET"])
def delete_attendance(attendance_id):
    db = get_db()
    db.execute("DELETE FROM attendance WHERE attendance_id = ?", (attendance_id,))
    db.commit()
    flash("Attendance record deleted.", "success")
    return redirect(url_for("attendance"))


@app.route("/membership-plans")
def membership_plans():
    plans = get_db().execute("SELECT * FROM membership_plans ORDER BY duration_months").fetchall()
    return render_template("membership_plans.html", plans=plans)


@app.route("/membership-plans/add", methods=["GET", "POST"])
def add_membership_plan():
    if request.method == "POST":
        try:
            get_db().execute(
                "INSERT INTO membership_plans(plan_name, duration_months, price) VALUES (?, ?, ?)",
                (request.form["plan_name"].strip(), int(request.form["duration_months"]), float(request.form["price"])),
            )
            get_db().commit()
            flash("Membership plan added.", "success")
            return redirect(url_for("membership_plans"))
        except (KeyError, ValueError, sqlite3.Error) as e:
            flash(f"Could not add plan: {e}", "error")
    return render_template("membership_plan_form.html")


@app.route("/memberships", methods=["GET", "POST"])
def memberships():
    db = get_db()
    members_list = db.execute("SELECT member_id, name FROM members ORDER BY name").fetchall()
    plans = db.execute("SELECT * FROM membership_plans ORDER BY duration_months").fetchall()
    if request.method == "POST":
        try:
            start = date.fromisoformat(request.form["start_date"])
            plan = db.execute(
                "SELECT * FROM membership_plans WHERE plan_id = ?", (request.form["plan_id"],)
            ).fetchone()
            if not plan:
                raise ValueError("Invalid membership plan.")
            # Month-aware end-date approximation without external dependencies.
            end = start
            for _ in range(plan["duration_months"]):
                next_month = end.month % 12 + 1
                next_year = end.year + (1 if end.month == 12 else 0)
                import calendar
                end = end.replace(
                    year=next_year, month=next_month,
                    day=min(end.day, calendar.monthrange(next_year, next_month)[1])
                )
            end = end - timedelta(days=1)
            db.execute(
                """INSERT INTO memberships(member_id, plan_id, start_date, end_date, status)
                   VALUES (?, ?, ?, ?, 'Active')""",
                (request.form["member_id"], plan["plan_id"], start.isoformat(), end.isoformat()),
            )
            db.commit()
            flash("Membership created successfully.", "success")
            return redirect(url_for("memberships"))
        except (KeyError, ValueError, sqlite3.Error) as e:
            flash(f"Could not create membership: {e}", "error")

    rows = db.execute(
        """SELECT ms.*, m.name, p.plan_name
           FROM memberships ms
           JOIN members m ON m.member_id = ms.member_id
           JOIN membership_plans p ON p.plan_id = ms.plan_id
           ORDER BY ms.membership_id DESC"""
    ).fetchall()
    return render_template("membership.html", members=members_list, plans=plans, memberships=rows)


@app.route("/payments", methods=["GET", "POST"])
def payments():
    db = get_db()
    members_list = db.execute("SELECT member_id, name FROM members ORDER BY name").fetchall()
    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
            if amount < 0:
                raise ValueError("Amount cannot be negative.")
            db.execute(
                """INSERT INTO payments(member_id, amount, payment_date, payment_method)
                   VALUES (?, ?, ?, ?)""",
                (request.form["member_id"], amount,
                 request.form.get("payment_date") or date.today().isoformat(),
                 request.form["payment_method"]),
            )
            db.commit()
            flash("Payment recorded successfully.", "success")
            return redirect(url_for("payments"))
        except (KeyError, ValueError, sqlite3.Error) as e:
            flash(f"Could not record payment: {e}", "error")
    rows = db.execute(
        """SELECT p.*, m.name FROM payments p
           JOIN members m ON m.member_id = p.member_id
           ORDER BY p.payment_date DESC, p.payment_id DESC"""
    ).fetchall()
    return render_template("payments.html", members=members_list, payments=rows)


@app.route("/trainers", methods=["GET", "POST"])
def trainers():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Trainer name is required.", "error")
        else:
            db.execute(
                "INSERT INTO trainers(name, phone, specialization) VALUES (?, ?, ?)",
                (name, request.form.get("phone", "").strip(), request.form.get("specialization", "").strip()),
            )
            db.commit()
            flash("Trainer added successfully.", "success")
            return redirect(url_for("trainers"))
    rows = db.execute("SELECT * FROM trainers ORDER BY trainer_id DESC").fetchall()
    return render_template("trainers.html", trainers=rows)


@app.route("/users")
def users():
    rows = get_db().execute("SELECT user_id, username, role FROM users ORDER BY user_id").fetchall()
    return render_template("users.html", users=rows)


@app.route("/reports")
def reports():
    rows = get_db().execute(
        """SELECT m.member_id, m.name, m.phone, p.plan_name,
                  ms.start_date, ms.end_date, ms.status
           FROM members m
           LEFT JOIN memberships ms
             ON ms.membership_id = (
                 SELECT MAX(m2.membership_id) FROM memberships m2
                 WHERE m2.member_id = m.member_id
             )
           LEFT JOIN membership_plans p ON p.plan_id = ms.plan_id
           ORDER BY m.member_id DESC"""
    ).fetchall()
    return render_template("reports.html", reports=rows)


# Backward-compatible route names used by older templates.
@app.route("/membership")
def membership_alias():
    return redirect(url_for("memberships"))


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", error="Page not found.", back_url=url_for("dashboard")), 404


@app.errorhandler(500)
def server_error(error):
    app.logger.exception("Unhandled application error")
    return render_template(
        "error.html",
        error="The server encountered an unexpected error. Check the terminal for details.",
        back_url=url_for("dashboard"),
    ), 500


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
