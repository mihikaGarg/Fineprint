"""All money is integer cents. Floats are rejected at the schema boundary."""

from typing import Annotated

from pydantic import Field, StrictInt

Cents = Annotated[StrictInt, Field(description="Amount in integer US cents.")]
NonNegativeCents = Annotated[StrictInt, Field(ge=0, description="Amount in integer US cents.")]
PositiveCents = Annotated[StrictInt, Field(gt=0, description="Amount in integer US cents.")]
