from collections import defaultdict
from flask import Flask, redirect
from flask import render_template
from flask import request
from flask import Response
from flask_httpauth import HTTPBasicAuth
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import io

from ast import literal_eval as make_tuple

import matplotlib

from gamelogic import Schedule


app = Flask(__name__)
auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username: str, password: str) -> bool:
    return username == "admin" and password == "admin"


@app.route("/")
def index() -> str:
    return render_template(
        "index.html",
        schedule=Schedule.load()
    )


@app.route("/admin", methods=("GET",))
@auth.login_required
def admin_get() -> str:
    return render_template("admin.html", schedule=Schedule.load())


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

    return "Deleted match " + match_id


@app.route("/admin/match", methods=("POST",))
@auth.login_required
def admin_match_add() -> str:
    schedule = Schedule.load()
    schedule.add_empty_match()
    schedule.save()

    return "Created match"


@app.route('/plot.png')
def plot_png():
    fig = create_figure()
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

def create_figure():
    schedule = Schedule.load()
    place_by_round = defaultdict(list)
    for round in range(1, schedule.get_current_round() + 1):
        table = schedule.calculate_table(up_to_round=round)
        for place, team in enumerate(table):
            place_by_round[team.name].append(place + 1)
    fig = Figure((12, 7),facecolor="#454545")
    axis = fig.add_subplot(1, 1, 1)
    axis.set_facecolor("#454545")
    axis.set_ylabel("Platzieung")
    axis.set_xlabel("Spiele")
    axis.invert_yaxis()
    axis.set_yticks(range(1, len(place_by_round) + 1))
    axis.set_xticks(range(1, place + 1))
    axis.grid(True, axis='y')

    xs = range(1, schedule.get_current_round() + 1)
    for i, team in enumerate(sorted(place_by_round)):
        ys = place_by_round[team]
        color = matplotlib.colors.hsv_to_rgb((i/(len(place_by_round) + 1), 1, 0.7 + 0.3 * (i % 2)))
        axis.plot(xs, ys, linewidth=4, color=color, label=team)
    
    # Shrink current axis by 20%
    box = axis.get_position()
    axis.set_position([box.x0, box.y0 + box.height * 0.1,
                 box.width, box.height * 0.9])

    frame = axis.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05),
          fancybox=True, shadow=True, ncol=5).get_frame()

    frame.set_facecolor("#929292")
    frame.set_edgecolor("#000000")
    return fig
        
