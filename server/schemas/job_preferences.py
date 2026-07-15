from typing import Literal
from pydantic import BaseModel, Field

class JobPreferences(BaseModel):
    target_roles: list[str] = Field(
        default_factory=list,
        description="Job titles the user wants to pursue.",
    )
    work_arrangement: Literal["remote", "hybrid", "on-site", "any"] = Field(
        default="any",
        description='Preferred work style: "remote", "hybrid", "on-site", or "any" if unspecified.',
    )
    location: str | None = Field(
        default=None,
        description="User's physical location or target region/timezone.",
    )
    salary: str | None = Field(
        default=None,
        description="Minimum acceptable compensation or hourly rate with currency symbol.",
    )
