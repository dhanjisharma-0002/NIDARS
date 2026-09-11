from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError, OperationalError

from extensions import db
from forms import LoginForm, RegisterForm
from models import ROLE_USER, User

auth_bp = Blueprint("auth", __name__)


def _database_unavailable_message():
    return "Database connection failed. Check MySQL and your .env settings, then try again."


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = (form.email.data or "").strip().lower()
        try:
            existing = User.query.filter_by(email=email).first()
        except Exception:
            db.session.rollback()
            try:
                db.create_all()
                existing = User.query.filter_by(email=email).first()
            except Exception:
                db.session.rollback()
                existing = None

        if existing:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for("auth.login"))

        user = User(
            name=(form.name.data or "").strip(),
            email=email,
            role=ROLE_USER,
        )
        user.set_password(form.password.data)

        try:
            db.session.add(user)
            db.session.commit()
            saved_user = User.query.filter_by(email=email).first()
            if not saved_user:
                current_app.logger.warning("User verification query failed immediately after commit for: %s", email)
        except Exception:
            db.session.rollback()
            try:
                db.create_all()
                db.session.add(user)
                db.session.commit()
                saved_user = User.query.filter_by(email=email).first()
                if not saved_user:
                    current_app.logger.warning("User verification query failed after retry for: %s", email)
            except IntegrityError:
                db.session.rollback()
                flash("An account with this email already exists. Please log in.", "warning")
                return redirect(url_for("auth.login"))
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception("Registration failed: %s", exc)
                flash(_database_unavailable_message(), "danger")
                return render_template("register.html", form=form)

        flash("Account created. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        ident = (form.email.data or "").strip().lower()
        user = None
        try:
            if "@" in ident:
                user = User.query.filter(User.email == ident).first()
            else:
                user = User.query.filter(
                    (User.email == ident) | (User.email == f"{ident}@nidars.gov.in")
                ).first()
        except Exception:
            db.session.rollback()
            try:
                db.create_all()
                if "@" in ident:
                    user = User.query.filter(User.email == ident).first()
                else:
                    user = User.query.filter(
                        (User.email == ident) | (User.email == f"{ident}@nidars.gov.in")
                    ).first()
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Login lookup failed due to database error")
                flash(_database_unavailable_message(), "danger")
                return render_template("login.html", form=form)

        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", form=form)

        login_user(user)
        flash("Logged in successfully.", "success")
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/") and not next_page.startswith("//"):
            return redirect(next_page)
        return redirect(url_for("main.dashboard"))

    return render_template("login.html", form=form)


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
