"""A small Days at Three Branches starter built entirely from ``sandbox.village``."""

from collections import deque

from sandbox.observation_types import ThreeBranchesAction, ThreeBranchesObservation
from sandbox.village import action, geometry, layout, me, people, props


def _cell_centre(cell: dict[str, int]) -> dict[str, float]:
    """Return the point at the centre of one village cell."""

    return {"x": cell["x"] + 0.5, "y": cell["y"] + 0.5}


class Agent:
    """Follows a role-specific work route and greets nearby villagers."""

    def reset(self, seed: int, observation: ThreeBranchesObservation) -> None:
        """Prepare for a day and assign this character's village role."""

        self.player_id = me.player_id(observation)
        self.role = self._role_for(self.player_id)
        self.stations = self._stations_for(observation)
        self.station_index = 0
        self.station_ticks = 0
        self.route: list[dict[str, float]] = []
        self.route_index = 0

    def _role_for(self, character_id: str) -> str:
        """Map a character identifier to its assigned village role."""

        index = int(character_id.split("_")[1])
        if index == 1:
            return "well_keeper"
        if index <= 5:
            return "farmer"
        if index <= 8:
            return "sweeper"
        return "wanderer"

    def _stations_for(self, observation: ThreeBranchesObservation) -> list[dict]:
        """Choose the ordered work stops for this villager's role."""

        home = me.home(observation)
        doorway = layout.doorway(observation, home) if home != "none" else None
        home_stop = self._station(doorway, "none", 12) if doorway is not None else None
        all_props = props.all(observation)

        if self.role == "well_keeper":
            pump = self._prop_with_type(all_props, "pump")
            return self._without_missing((home_stop, self._prop_station(observation, pump, "use", 45)))

        if self.role == "farmer":
            plots = [prop for prop in all_props if prop["type"] == "plot"]
            player_number = int(self.player_id.split("_")[1])
            plot = plots[(player_number - 2) % len(plots)] if plots else None
            pump = self._prop_with_type(all_props, "pump")
            return self._without_missing(
                (home_stop, self._prop_station(observation, pump, "use", 12), self._prop_station(observation, plot, "use", 90))
            )

        if self.role == "sweeper":
            lanterns = [prop for prop in all_props if prop["type"] == "lantern"]
            player_number = int(self.player_id.split("_")[1])
            first = (player_number - 6) % len(lanterns) if lanterns else 0
            patrol = [lanterns[(first + offset) % len(lanterns)] for offset in (0, 2, 4)] if lanterns else []
            return self._without_missing(
                (home_stop, *(self._prop_station(observation, lantern, "sweep", 30) for lantern in patrol))
            )

        shrine = self._prop_with_type(all_props, "shrine")
        board = self._prop_with_type(all_props, "board")
        return self._without_missing(
            (home_stop, self._prop_station(observation, board, "none", 20), self._prop_station(observation, shrine, "use", 30))
        )

    def _prop_with_type(self, all_props: tuple, prop_type: str):
        """Return the first static prop with a given type, if one exists."""

        return next((prop for prop in all_props if prop["type"] == prop_type), None)

    def _prop_station(self, observation: ThreeBranchesObservation, prop: dict | None, job: str, duration: int):
        """Create a reachable work stop beside a prop rather than inside its collision shape."""

        if prop is None:
            return None
        point = self._nearest_walkable_cell(observation, prop["cell"])
        return None if point is None else {"point": point, "prop": prop["id"], "job": job, "duration": duration}

    def _station(self, point: dict[str, float], job: str, duration: int) -> dict:
        return {"point": point, "prop": None, "job": job, "duration": duration}

    def _without_missing(self, stations: tuple) -> list[dict]:
        """Discard optional landmarks that are absent from a village layout."""

        return [station for station in stations if station is not None]

    def _nearest_walkable_cell(self, observation: ThreeBranchesObservation, cell: dict[str, int]) -> dict[str, float] | None:
        """Find a walkable cell close enough to reach and use a prop."""

        for radius in range(1, 5):
            candidates = (
                {"x": cell["x"] + dx, "y": cell["y"] + dy}
                for dx in range(-radius, radius + 1)
                for dy in range(-radius, radius + 1)
                if max(abs(dx), abs(dy)) == radius
            )
            for candidate in candidates:
                if layout.walkable(observation, candidate):
                    return _cell_centre(candidate)
        return None

    def _route_to(self, observation: ThreeBranchesObservation, destination: dict[str, float]) -> list[dict[str, float]]:
        """Build a collision-safe cardinal path from the current cell to a work stop."""

        start = layout.cell_at(observation, me.position(observation))
        goal = layout.cell_at(observation, destination)
        if start is None or goal is None:
            return []

        start_key = (start["x"], start["y"])
        goal_key = (goal["x"], goal["y"])
        frontier = deque([start_key])
        previous = {start_key: None}
        while frontier and goal_key not in previous:
            current = frontier.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbour = (current[0] + dx, current[1] + dy)
                if neighbour in previous:
                    continue
                current_cell = {"x": current[0], "y": current[1]}
                neighbour_cell = {"x": neighbour[0], "y": neighbour[1]}
                if layout.can_step(observation, current_cell, neighbour_cell):
                    previous[neighbour] = current
                    frontier.append(neighbour)

        if goal_key not in previous:
            return []
        cells = []
        current = goal_key
        while current != start_key:
            cells.append({"x": current[0], "y": current[1]})
            current = previous[current]
        return [_cell_centre(cell) for cell in reversed(cells)]

    def act(self, observation: ThreeBranchesObservation) -> ThreeBranchesAction:
        """Choose one simple order from current sight and standing village knowledge."""

        here = me.position(observation)
        heading = me.heading(observation)
        if not self.stations:
            return action.stand(heading, "none")

        station = self.stations[self.station_index]
        if geometry.distance(here, station["point"]) <= 0.2:
            self.station_ticks += 1
            if self.station_ticks > station["duration"]:
                self.station_index = (self.station_index + 1) % len(self.stations)
                self.station_ticks = 0
                self.route = []
                self.route_index = 0
                station = self.stations[self.station_index]
            else:
                usable = props.usable(observation)
                if station["job"] == "use" and usable is not None and usable["id"] == station["prop"]:
                    return action.stand(heading, "use")
                return action.stand(heading, station["job"])

        if not self.route:
            self.route = self._route_to(observation, station["point"])
            self.route_index = 0
        if self.route_index < len(self.route):
            waypoint = self.route[self.route_index]
            if geometry.distance(here, waypoint) <= 0.2:
                self.route_index += 1
                return action.stand(heading, "none")
            expression = "wave" if people.seen(observation) else "none"
            return action.walk(geometry.heading_to(here, waypoint), 1.0, expression)

        return action.stand(heading, "none")

    # Optional: messaging. On your turn, chat receives messages addressed to your player since
    # its previous turn. Return messages with a recipient and text, or nothing to stay silent.
    # Use None as the recipient to broadcast. Every message is recorded and shown in replays.
    #
    # def chat(self, inbox: list[dict]) -> list[dict] | None:
    #     ...
