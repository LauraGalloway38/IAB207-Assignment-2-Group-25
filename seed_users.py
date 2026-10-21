from pathlib import Path

from werkzeug.security import generate_password_hash, check_password_hash

from nightbite import create_app, db
from nightbite.models import User


# Use the database that will be included in the submission package.
database_path = Path(__file__).resolve().parent / "nightbite" / "sitedata.sqlite"
app = create_app({
    "SQLALCHEMY_DATABASE_URI": "sqlite:///" + database_path.as_posix()
})

# Fictional accounts for testing and marking.
demo_users = [
    {
        "name": "Alex Demo",
        "email": "alex.demo@example.com",
        "contact_number": "0400000001",
        "street_address": "1 Example Street, Brisbane QLD 4000",
        "password": "NightbiteDemo1!",
    },
    {
        "name": "Sam Demo",
        "email": "sam.demo@example.com",
        "contact_number": "0400000002",
        "street_address": "2 Example Street, Brisbane QLD 4000",
        "password": "NightbiteDemo2!",
    },
]


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Leave existing accounts unchanged when this script is run again.
        for details in demo_users:
            user = db.session.scalar(
                db.select(User).where(User.email == details["email"])
            )

            if user is not None:
                print(f"Already exists: {user.email}")
                continue

            user = User(
                name=details["name"],
                email=details["email"],
                contact_number=details["contact_number"],
                street_address=details["street_address"],
                password_hash=generate_password_hash(details["password"]),
            )
            db.session.add(user)

        db.session.commit()

        # Verify the saved accounts against the documented demo passwords.
        for details in demo_users:
            user = db.session.scalar(
                db.select(User).where(User.email == details["email"])
            )
            matches = check_password_hash(
                user.password_hash, details["password"]
            )
            result = "PASS" if matches else "PASSWORD DIFFERS"
            print(f"{result}: {user.email}")

        print(f"Database: {database_path}")