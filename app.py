from flask import Flask, render_template, request, redirect, flash, session
import psycopg2


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

# Secret key for sessions and flash messages
app.secret_key = "gym-secret-key"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    return psycopg2.connect(
        host="localhost",
        port="5432",
        database="gym_management",
        user="postgres",
        password="Vishwas@160627"
    )


# ============================================================
# LOGIN PROTECTION
# ============================================================

@app.before_request
def require_login():

    # These pages can be opened without login
    allowed_routes = [
        "login",
        "static"
    ]

    # Allow login page and static files
    if request.endpoint in allowed_routes:
        return

    # If user is not logged in, send them to login
    if "user_id" not in session:
        return redirect("/login")


# ============================================================
# LOGIN PAGE
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    # If already logged in, go to dashboard
    if "user_id" in session:
        return redirect("/")

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Check empty fields
        if username == "" or password == "":

            flash(
                "Please enter username and password.",
                "error"
            )

            return render_template("login.html")

        conn = None
        cur = None

        try:

            conn = get_db_connection()
            cur = conn.cursor()

            # Check username and password
            cur.execute(
                """
                SELECT
                    user_id,
                    username,
                    password,
                    role
                FROM users
                WHERE username = %s
                AND password = %s
                """,
                (
                    username,
                    password
                )
            )

            user = cur.fetchone()

            # User found
            if user:

                session["user_id"] = user[0]
                session["username"] = user[1]
                session["role"] = user[3]

                flash(
                    "Login successful!",
                    "success"
                )

                return redirect("/")

            # User not found
            else:

                flash(
                    "Invalid username or password.",
                    "error"
                )

        except Exception as e:

            flash(
                "Database error: " + str(e),
                "error"
            )

        finally:

            if cur:
                cur.close()

            if conn:
                conn.close()

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    # Remove login session
    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect("/login")


# ============================================================
# HOME / DASHBOARD
# ============================================================

@app.route("/")
def index():

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        # ----------------------------------------------------
        # Count Members
        # ----------------------------------------------------

        cur.execute(
            "SELECT COUNT(*) FROM members"
        )

        members_count = cur.fetchone()[0]

        # ----------------------------------------------------
        # Count Trainers
        # ----------------------------------------------------

        cur.execute(
            "SELECT COUNT(*) FROM trainers"
        )

        trainers_count = cur.fetchone()[0]

        # ----------------------------------------------------
        # Count Memberships
        # ----------------------------------------------------

        cur.execute(
            "SELECT COUNT(*) FROM memberships"
        )

        memberships_count = cur.fetchone()[0]

        # ----------------------------------------------------
        # Count Payments
        # ----------------------------------------------------

        cur.execute(
            "SELECT COUNT(*) FROM payments"
        )

        payments_count = cur.fetchone()[0]

        cur.close()
        conn.close()

        return render_template(
            "index.html",
            members_count=members_count,
            trainers_count=trainers_count,
            memberships_count=memberships_count,
            payments_count=payments_count
        )

    except Exception as e:

        return render_template(
            "error.html",
            error=str(e),
            back_url="/"
        )


# ============================================================
# GENERIC VIEW TABLE FUNCTION
# ============================================================

def show_table(table_name, title):

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        # Get all records
        query = f'''
            SELECT *
            FROM "{table_name}"
            ORDER BY 1
        '''

        cur.execute(query)

        data = cur.fetchall()

        # Get column names
        columns = [
            description[0]
            for description in cur.description
        ]

        cur.close()
        conn.close()

        return render_template(
            "table.html",
            title=title,
            data=data,
            columns=columns
        )

    except Exception as e:

        return render_template(
            "error.html",
            error=str(e),
            back_url="/"
        )


# ============================================================
# VIEW MEMBERS
# ============================================================

@app.route("/members")
def members():

    return show_table(
        "members",
        "Gym Members"
    )


# ============================================================
# VIEW ATTENDANCE
# ============================================================

@app.route("/attendance")
def attendance():

    return show_table(
        "attendance",
        "Attendance"
    )


# ============================================================
# VIEW MEMBERSHIPS
# ============================================================

@app.route("/memberships")
def memberships():

    return show_table(
        "memberships",
        "Memberships"
    )


# ============================================================
# VIEW TRAINERS
# ============================================================

@app.route("/trainers")
def trainers():

    return show_table(
        "trainers",
        "Gym Trainers"
    )


# ============================================================
# VIEW MEMBERSHIP PLANS
# ============================================================

@app.route("/membership-plans")
def membership_plans():

    return show_table(
        "membership_plans",
        "Membership Plans"
    )


# ============================================================
# VIEW PAYMENTS
# ============================================================

@app.route("/payments")
def payments():

    return show_table(
        "payments",
        "Payments"
    )


# ============================================================
# VIEW USERS
# ============================================================

@app.route("/users")
def users():

    return show_table(
        "users",
        "Users"
    )


# ============================================================
# GET TABLE COLUMNS
# ============================================================

def get_table_columns(table_name):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default,
            is_identity
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,)
    )

    columns = cur.fetchall()

    cur.close()
    conn.close()

    result = []

    for column in columns:

        column_name = column[0]
        data_type = column[1]
        nullable = column[2]
        default_value = column[3]
        is_identity = column[4]

        # ----------------------------------------------------
        # Skip identity columns
        # ----------------------------------------------------

        if is_identity == "YES":
            continue

        # ----------------------------------------------------
        # Skip SERIAL / auto-generated ID columns
        # ----------------------------------------------------

        if default_value and "nextval(" in default_value:
            continue

        result.append(
            {
                "name": column_name,
                "type": data_type,
                "nullable": nullable == "YES",
                "default": default_value
            }
        )

    return result


# ============================================================
# ADD RECORD - GENERIC FUNCTION
# ============================================================

def add_record(table_name, title, back_url):

    try:

        columns = get_table_columns(table_name)

    except Exception as e:

        return render_template(
            "error.html",
            error=str(e),
            back_url=back_url
        )

    # ========================================================
    # POST REQUEST
    # ========================================================

    if request.method == "POST":

        conn = None
        cur = None

        try:

            conn = get_db_connection()
            cur = conn.cursor()

            insert_columns = []
            insert_values = []
            placeholders = []

            # ------------------------------------------------
            # READ FORM VALUES
            # ------------------------------------------------

            for column in columns:

                column_name = column["name"]

                value = request.form.get(
                    column_name,
                    ""
                ).strip()

                # --------------------------------------------
                # EMPTY FIELD WITH DEFAULT VALUE
                # --------------------------------------------

                if value == "" and column["default"]:
                    continue

                # --------------------------------------------
                # EMPTY NULLABLE FIELD
                # --------------------------------------------

                if value == "" and column["nullable"]:
                    continue

                # --------------------------------------------
                # REQUIRED FIELD EMPTY
                # --------------------------------------------

                if value == "" and not column["nullable"]:

                    cur.close()
                    conn.close()

                    flash(
                        f"Please enter {column_name.replace('_', ' ')}",
                        "error"
                    )

                    return render_template(
                        "add_record.html",
                        title=title,
                        columns=columns,
                        back_url=back_url
                    )

                # --------------------------------------------
                # ADD VALUE
                # --------------------------------------------

                insert_columns.append(column_name)

                insert_values.append(value)

                placeholders.append("%s")

            # =================================================
            # INSERT DATA
            # =================================================

            if insert_columns:

                column_names = ", ".join(
                    f'"{column}"'
                    for column in insert_columns
                )

                query = f"""
                    INSERT INTO "{table_name}"
                    ({column_names})
                    VALUES ({", ".join(placeholders)})
                """

                cur.execute(
                    query,
                    insert_values
                )

                conn.commit()

            # ------------------------------------------------
            # CLOSE CONNECTION
            # ------------------------------------------------

            cur.close()
            conn.close()

            flash(
                f"{title} added successfully!",
                "success"
            )

            return redirect(back_url)

        # ====================================================
        # DATABASE ERROR
        # ====================================================

        except Exception as e:

            if conn:
                conn.rollback()

            if cur:
                cur.close()

            if conn:
                conn.close()

            return render_template(
                "error.html",
                error=str(e),
                back_url=back_url
            )

    # ========================================================
    # GET REQUEST
    # ========================================================

    return render_template(
        "add_record.html",
        title=title,
        columns=columns,
        back_url=back_url
    )


# ============================================================
# ADD MEMBER
# ============================================================

@app.route(
    "/members/add",
    methods=["GET", "POST"]
)
def add_member():

    return add_record(
        "members",
        "New Member",
        "/members"
    )


# ============================================================
# ADD ATTENDANCE
# ============================================================

@app.route(
    "/attendance/add",
    methods=["GET", "POST"]
)
def add_attendance():

    return add_record(
        "attendance",
        "Attendance Record",
        "/attendance"
    )


# ============================================================
# ADD MEMBERSHIP
# ============================================================

@app.route(
    "/memberships/add",
    methods=["GET", "POST"]
)
def add_membership():

    return add_record(
        "memberships",
        "New Membership",
        "/memberships"
    )


# ============================================================
# ERROR HANDLER
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "error.html",
        error="Page not found.",
        back_url="/"
    ), 404


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )