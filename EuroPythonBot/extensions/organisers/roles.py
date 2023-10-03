"""Data structure for role IDs."""
import attrs


@attrs.define
class Roles:
    """Role mapping for the organisers extension."""

    moderators: int
    organisers: int
    volunteers: int
    speakers: int
    sponsors: int
    participants: int
    participants_remote: int
