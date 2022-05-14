from flask import Flask, redirect
from flask import render_template
from flask import request

from flask_httpauth import HTTPBasicAuth

from ast import literal_eval as make_tuple

from gamelogic import Schedule


app = Flask(__name__)
auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username: str, password: str) -> bool:
    return username == "admin" and password == "admin"


@app.route("/")
def index() -> str:
    schedule = Schedule.load()
    return render_template(
        "index.html",
        matches=schedule.matches,
        teams=schedule.calculate_table(),
        predictions=schedule.predict_matches(),
    )


@app.route("/admin", methods=("GET",))
@auth.login_required
def admin_get() -> str:
    return render_template("admin.html", matches=Schedule.load().matches)


@app.route("/admin", methods=("POST",))
@auth.login_required
def admin_post() -> str:
    schedule = Schedule.load()

    for key, value in request.form.items():
        try:
            match_id, attribute_name = make_tuple(key)
            if value == "":
                continue

            match = schedule.get_match(match_id)
            match.set_attribute(attribute_name, value)

        except Exception as e:
            continue

    # Save matches
    schedule.save()

    return redirect("admin", code=302)


@app.route("/admin/match/<match_id>", methods=("DELETE",))
@auth.login_required
def admin_match_delete(match_id) -> str:
    schedule = Schedule.load()
    match = schedule.get_match(match_id)
    schedule.matches.remove(match)
    schedule.save()

    return redirect("admin", code=302)


@app.route("/admin/match", methods=("POST",))
@auth.login_required
def admin_match_add() -> str:
    schedule = Schedule.load()
    schedule.add_empty_match()
    schedule.save()

    return redirect("admin", code=302)
