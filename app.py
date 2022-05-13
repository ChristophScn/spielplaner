import pickle
from flask import Flask
from flask import render_template
from flask import request
import itertools
import random
from ast import literal_eval as make_tuple
import uuid

from torch import rand

app = Flask(__name__)


class Match(object):
    def __init__(self, time, home, guest, goals, goals_against, referee, round) -> None:
        self.time = time
        self.home = home
        self.guest = guest
        self.goals = goals
        self.goals_against = goals_against
        self.referee = referee
        self.round = round
        self.id = str(uuid.uuid4())

    def add_referee(self, matches):
        if self.referee is not None:
            return
        matches = matches[:]
        match_index = matches.index(self)
        table = calculate_table(matches)
        table.sort(key=lambda match: match.referee_count)
        matches += predict_matches(matches, add_referees=False)
        for i in range(len(table)):
            referee = table[i]
            if referee.name not in (
                matches[match_index - 1].get_teams()
                | self.get_teams()
                | matches[match_index + 1].get_teams()
            ):
                self.referee = referee.name
                break

    def get_teams(self):
        return set((self.home, self.guest))

    def is_played(self):
        return not (self.goals is None and self.goals_against is None)

    def __repr__(self):
        return f"{self.id}"

    def set_attribute(self, name, value):
        if name == "time":
            self.time = int(value)
        if name == "round":
            self.round = int(value)
        elif name == "home":
            self.home = str(value)
        elif name == "guest":
            self.guest = str(value)
        elif name == "goals":
            self.goals = int(value) if value else None
        elif name == "goals_against":
            self.goals_against = int(value) if value else None
        elif name == "referee":
            self.referee = str(value)


class Team(object):
    def __init__(self, name):
        self.name = name
        self.games = 0
        self.wins = 0
        self.draws = 0
        self.loses = 0
        self.goals = 0
        self.goals_against = 0
        self.points = 0
        self.goal_difference = 0
        self.referee_count = 0

    def add_match(self, match):
        if match.referee == self.name:
            self.referee_count += 1

        if not match.is_played():
            return

        if match.home != self.name and match.guest != self.name:
            return

        goals = match.goals if match.home == self.name else match.goals_against
        goals_against = match.goals_against if match.home == self.name else match.goals

        self.games += 1
        self.wins += 1 if goals > goals_against else 0
        self.draws += 1 if goals == goals_against else 0
        self.loses += 1 if goals < goals_against else 0
        self.goals += goals
        self.goals_against += goals_against

        # Calculate from scratch to prevent inconsistent state
        self.goal_difference = self.goals - self.goals_against
        self.points = 3 * self.wins + 1 * self.draws

    def __repr__(self):
        return self.name


TEAMS = [
    "Hippos A",
    "Hippos B",
    "Hippos C",
    "CCC Barsinghausen",
    "Oldenburg/Münster (D)",
    "Limmer",
    "RSV A",
    "RSV B",
    "Rostock",
    "Buxburg",
    "Braunschweig",
    "Erlangen",
]


def get_match(matches: list, id):
    for match in matches:
        if match.id == id:
            return match
    raise KeyError(f"No match with id: {id}")


def match_exists(matches: list, team1, team2):
    for match in matches:
        if set((team1.name, team2.name)) == match.get_teams():
            return True
    return False


def generate_first_round():

    random.seed(0)
    matches = []
    time = 0
    teams = TEAMS[:]
    random.shuffle(teams)

    for i in range(0, len(teams) - 1, 2):
        matches.append(Match(0, teams[i], teams[i + 1], None, None, None, 1))

    random.shuffle(matches)

    for match in matches:
        match.add_referee(matches)
        match.time = time
        time += 25

    return matches


def predict_matches(matches, add_referees=True):
    if not matches:
        return generate_first_round()

    new_matches = []
    table = calculate_table(matches)

    time = matches[-1].time + 5
    round = matches[-1].round + 1

    while table:
        home = table.pop(0)
        for team in table:
            if not match_exists(matches, home, team):
                break
        else:  # Did not break
            team = table[0]

        new_matches.append(
            Match(
                time,
                home.name,
                team.name,
                None,
                None,
                None,
                round,
            )
        )
        time += 25
        table.remove(team)
    if add_referees:
        for match in new_matches:
            match.add_referee(matches + new_matches)
    return new_matches


def calculate_table(matches):
    teams = set()
    for match in matches:
        teams.add(match.home)
        teams.add(match.guest)
    table = []
    for name in teams:
        team = Team(name)
        table.append(team)
        for match in matches:
            team.add_match(match)

    table.sort(
        key=lambda team: (team.points, team.goal_difference, team.goals, team.name),
        reverse=True,
    )

    return table


def all_matches_played(matches):
    return all(match.is_played() for match in matches)


@app.route("/")
def index() -> str:
    matches = pickle.load(open("matches.p", "rb"))
    return render_template(
        "index.html",
        matches=matches,
        teams=calculate_table(matches),
        predictions=predict_matches(matches),
    )


@app.route("/admin/start")
def admin_start() -> str:
    try:
        pickle.load(open("matches.p", "rb"))
        # return "Already started"
    except:
        pass
    pickle.dump(generate_first_round(), open("matches.p", "wb"))
    return "Started"


@app.route("/admin", methods=("GET",))
def admin_get() -> str:
    matches = pickle.load(open("matches.p", "rb"))
    return render_template("admin.html", matches=matches)


@app.route("/admin", methods=("POST",))
def admin_post() -> str:
    matches = pickle.load(open("matches.p", "rb"))

    for key, value in request.form.items():
        try:
            match_id, attribute_name = make_tuple(key)
            if value == "":
                continue
            match = get_match(matches, match_id)
            match.set_attribute(attribute_name, value)
        except Exception as e:
            print(e)
            continue

    matches.sort(key=lambda match: match.time)

    if all_matches_played(matches):
        matches += predict_matches(matches)

    pickle.dump(matches, open("matches.p", "wb"))
    # write to matches
    return admin_get()
