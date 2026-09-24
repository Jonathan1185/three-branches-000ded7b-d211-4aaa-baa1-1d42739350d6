"""A small Days at Three Branches starter built entirely from ``sandbox.village``."""

from sandbox.observation_types import ThreeBranchesAction, ThreeBranchesObservation
from sandbox.village import action, geometry, layout, me, people, props


def _cell_centre(cell: dict[str, int]) -> dict[str, float]:
    """Return the point at the centre of one village cell."""

    return {"x": cell["x"] + 0.5, "y": cell["y"] + 0.5}


class Agent:
    """Walks out of its home, visits the pump, and acknowledges people it sees."""

    def reset(self, seed: int, observation: ThreeBranchesObservation) -> None:
        """Prepare for a day and assign this character's village role."""

        self.role = self._role_for(me.player_id(observation))

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

    def act(self, observation: ThreeBranchesObservation) -> ThreeBranchesAction:
        """Choose one simple order from current sight and standing village knowledge."""

        heading = me.heading(observation)
        seen_people = people.seen(observation)
        if seen_people:
            # Greet the first visible villager face-to-face before resuming the routine.
            person = seen_people[0]
            return action.stand(geometry.heading_to(me.position(observation), person["position"]), "wave")

        usable = props.usable(observation)
        if usable is not None and usable["type"] == "bench":
            return action.stand(heading, "use")

        here = me.position(observation)
        expression = "none"
        home = me.home(observation)
        door = layout.doorway(observation, home) if home != "none" else None
        here_cell = layout.cell_at(observation, here)
        if (
            door is not None
            and here_cell is not None
            and layout.ground_at(observation, here_cell) == "interior"
        ):
            return action.walk(geometry.heading_to(here, door), 1.0, expression)

        pump = next((prop for prop in props.all(observation) if prop["type"] == "pump"), None)
        if pump is not None:
            return action.walk(geometry.heading_to(here, _cell_centre(pump["cell"])), 1.0, expression)
        return action.walk(heading, 0.0, expression)

    # Optional: messaging. On your turn, chat receives messages addressed to your player since
    # its previous turn. Return messages with a recipient and text, or nothing to stay silent.
    # Use None as the recipient to broadcast. Every message is recorded and shown in replays.
    #
    # def chat(self, inbox: list[dict]) -> list[dict] | None:
    #     ...
