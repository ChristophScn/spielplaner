import json
import pickle
import uuid
import random
import datetime


class Match(object):
    def __init__(
        self,
        time,
        home,
        guest,
        goals,
        goals_against,
        referee,
        round,
        id=None,
        placement=None,
    ) -> None:
        self.time = time
        self.home = home
        self.guest = guest
        self.goals = goals
        self.goals_against = goals_against
        self.referee = referee
        self.round = round
        self.id = str(uuid.uuid4()) if not id else id
        self.placement = placement

    def set_attribute(self, name, value):
        if name == "time":
            try:
                self.time = datetime.datetime.strptime(value, "%d %H:%M")
            except ValueError as e:
                new_time = datetime.datetime.strptime(value, "%H:%M")
                self.time = datetime.datetime(
                    self.time.year,
                    self.time.month,
                    self.time.day,
                    new_time.hour,
                    new_time.minute,
                )
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
        elif name == "round":
            self.round = int(value)

    def get_teams(self) -> set["Team"]:
        return set((self.home, self.guest))

    def is_played(self):
        return not (self.goals is None or self.goals_against is None)

    def add_referee(self, schedule: "Schedule", new_matches=[]) -> None:

        if self.referee is not None:
            return

        matches = schedule.matches + new_matches
        match_index = matches.index(self)
        table = schedule.calculate_table(additional_matches=new_matches)
        table.sort(key=lambda team: team.referee_count)
        matches += schedule.predict_matches(add_referees=False)
        for i in range(len(table)):
            referee = table[i]
            if referee.name not in (
                matches[match_index - 1].get_teams()
                | self.get_teams()
                | matches[match_index + 1].get_teams()
            ):
                self.referee = referee.name
                return

    def __repr__(self):
        return f"Match({self.time},{self.home},{self.guest},{self.goals},{self.goals_against},{self.referee},{self.round},{self.id},{self.placement})"


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


class Schedule(object):
    def __init__(
        self,
        teams=TEAMS,
        start_time=datetime.datetime(1900, 1, 1, 8, 30),
        match_time=datetime.timedelta(minutes=25),
        pause_time=datetime.timedelta(minutes=5),
        end_time=datetime.datetime(1900, 1, 1, 19, 00),
        rounds=5,
        announcement="",
    ) -> None:

        self.teams = teams
        self.start_time = start_time
        self.match_time = match_time
        self.pause_time = pause_time
        self.end_time = end_time
        self.rounds = rounds
        self.announcement = announcement

        self.generate_first_round()

    def generate_first_round(self):
        random.seed(0)

        self.matches: list[Match] = []
        time = self.start_time

        teams = self.teams[:]
        random.shuffle(teams)

        for i in range(0, len(teams) - 1, 2):
            self.matches.append(Match(0, teams[i], teams[i + 1], None, None, None, 1))

        random.shuffle(self.matches)

        for match in self.matches:
            match.time = time
            time += self.match_time

        for match in self.matches:
            match.add_referee(self)

        self.save()

    def get_match(self, id: str) -> Match:
        for match in self.matches:
            if match.id == id:
                return match

        raise KeyError(f"No match with id: {id}")

    def match_exists(self, team1: Team, team2: Team):
        for match in self.matches:
            if set((team1.name, team2.name)) == match.get_teams():
                return True

        return False

    def get_last_match_time(self) -> datetime.datetime:
        return self.start_time if not self.matches else self.matches[-1].time

    def get_current_round(self) -> datetime.datetime:
        return max(self.matches, key=lambda match: match.round).round

    def wrap_time(self, time):
        if (
            time.hour > self.end_time.hour
            or time.minute > self.end_time.minute
            and time.hour == self.end_time.hour
        ):
            return datetime.datetime(
                time.year,
                time.month,
                time.day + 1,
                self.start_time.hour,
                self.start_time.minute,
            )
        else:
            return time

    def more_rounds(self):
        return (
            self.get_current_round() < self.rounds + 1
        )  # Rounds and one placement round

    def predict_matches(self, add_referees=True) -> list[Match]:
        if not self.matches:
            self.generate_first_round()

        if len(self.calculate_table()) % 2 == 1:
            return [
                Match(
                    self.start_time,
                    "Ungerade Anzahl an Teams",
                    "Ungerade Anzahl an Teams",
                    None,
                    None,
                    None,
                    self.get_current_round() + 1,
                )
            ]

        new_matches = []
        table = self.calculate_table()

        time = self.get_last_match_time() + self.match_time + self.pause_time
        round = self.get_current_round() + 1

        if round <= self.rounds:
            while table:
                home = table.pop(0)
                for team in table:
                    if not self.match_exists(home, team):
                        break
                else:  # Did not break
                    team = table[0]

                time = self.wrap_time(time)

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

                time += datetime.timedelta(minutes=25)
                table.remove(team)

        elif round == self.rounds + 1:
            referee_final_lookup = {
                5: 1,
                7: 3,
                9: 4,
                11: 2,
                3: 6,
                1: 5,
            }
            for i in [k for k in range(4, len(table) - 1, 2)] + [2, 0]:
                time = self.wrap_time(time)
                new_matches.append(
                    Match(
                        time,
                        table[i].name,
                        table[i + 1].name,
                        None,
                        None,
                        table[referee_final_lookup[i + 1] - 1].name
                        if i + 1 in referee_final_lookup
                        else None,
                        round,
                        placement=i + 1,
                    )
                )
                time += datetime.timedelta(minutes=25)

        if add_referees:
            for match in new_matches:
                match.add_referee(self, new_matches=new_matches)

        return new_matches

    def calculate_table(self, additional_matches=[], up_to_round=None):
        up_to_round = self.rounds if up_to_round is None else up_to_round

        teams = set()
        matches = self.matches + additional_matches

        for match in matches:
            teams.add(match.home)
            teams.add(match.guest)
        table = []
        for name in teams:
            team = Team(name)
            table.append(team)
            for match in matches:
                if match.round <= up_to_round:
                    team.add_match(match)

        table.sort(
            key=lambda team: (team.points, team.goal_difference, team.goals, team.name),
            reverse=True,
        )

        return table

    def calculate_final_table(self):
        table = []
        for match in self.matches:
            if match.placement is not None and match.is_played():
                table.append(
                    (
                        match.placement
                        if match.goals >= match.goals_against
                        else match.placement + 1,
                        match.home,
                    )
                )
                table.append(
                    (
                        match.placement
                        if match.goals_against >= match.goals
                        else match.placement + 1,
                        match.guest,
                    )
                )
        table.sort()

        return table

    def all_matches_played(self):
        return all(match.is_played() for match in self.matches)

    def get_graph_data(self):
        for team in self.teams:
            data = [(game_nr, 0) for game_nr in range(self.get_current_round())]
        return data

    @classmethod
    def load(cls) -> "Schedule":
        try:
            return pickle.load(open("schedule.p", "rb"))
        except:
            return cls()

    def save(self) -> None:
        self.matches.sort(key=lambda match: match.time)

        if not self.matches:
            self.generate_first_round()

        if self.all_matches_played():
            self.matches += self.predict_matches()

        pickle.dump(self, open("schedule.p", "wb"))

    def add_empty_match(self) -> None:
        self.matches.append(
            Match(
                self.get_last_match_time() + self.match_time,
                "Team 1",
                "Team 2",
                None,
                None,
                None,
                self.get_current_round(),
            )
        )

    def toJson(self):
        return json.dumps(
            self,
            default=lambda o: o.__dict__
            if type(o) not in (datetime.datetime, datetime.timedelta)
            else str(o),
            sort_keys=True,
            indent=4,
        )

    @classmethod
    def fromJson(cls, json_str: str) -> "Schedule":
        json_obj = json.loads(json_str)

        if "start_time" in json_obj:
            json_obj["start_time"] = datetime.datetime.strptime(
                json_obj["start_time"], "%Y-%m-%d  %H:%M:%S"
            )
        if "match_time" in json_obj:
            t = datetime.datetime.strptime(json_obj["match_time"], "%H:%M:%S")
            json_obj["match_time"] = datetime.timedelta(
                hours=t.hour, minutes=t.minute, seconds=t.second
            )
        if "pause_time" in json_obj:
            t = datetime.datetime.strptime(json_obj["pause_time"], "%H:%M:%S")
            json_obj["pause_time"] = datetime.timedelta(
                hours=t.hour, minutes=t.minute, seconds=t.second
            )
        if "end_time" in json_obj:
            json_obj["end_time"] = datetime.datetime.strptime(
                json_obj["end_time"], "%Y-%m-%d  %H:%M:%S"
            )
        if "rounds" in json_obj:
            json_obj["rounds"] = json_obj["rounds"]
        if "matches" in json_obj:
            matches = json_obj["matches"]
            del json_obj["matches"]
        else:
            matches = None

        schedule = Schedule(**json_obj)

        if matches:
            matches_list = []
            for match in matches:
                if "time" in match:
                    match["time"] = datetime.datetime.strptime(
                        match["time"], "%Y-%m-%d  %H:%M:%S"
                    )

                matches_list.append(Match(**match))

            schedule.matches = matches_list

        return schedule
