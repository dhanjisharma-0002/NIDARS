from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


class RegisterForm(FlaskForm):
    name = StringField(
        "Full name",
        validators=[
            DataRequired(message="Name is required."),
            Length(min=2, max=100, message="Name must be between 2 and 100 characters."),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
            Length(max=255),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, max=128, message="Password must be between 8 and 128 characters."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords do not match."),
        ],
    )
    submit = SubmitField("Create account")

    def validate_email(self, field):
        value = (field.data or "").strip().lower()
        field.data = value
        if not value:
            raise ValidationError("Email is required.")


class LoginForm(FlaskForm):
    email = StringField(
        "Username or Email",
        validators=[
            DataRequired(message="Username or email is required."),
            Length(max=255),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
    )
    submit = SubmitField("Log in")

    def validate_email(self, field):
        field.data = (field.data or "").strip().lower()

