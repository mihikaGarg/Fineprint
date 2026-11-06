from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Base for every contract: immutable, no unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")
