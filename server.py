import argparse
import re
import secrets
from decimal import Decimal
from fractions import Fraction
from math import ceil, floor
from typing import Annotated, TypedDict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

MAX_SAFE_INTEGER = 2**53 - 1
MAX_COUNT = 100
MAX_SIDES = 1_000_000
DICE_PATTERN = re.compile(
    r"(?P<count>[0-9]{0,3})d(?P<sides>%|[0-9]{1,7})(?P<modifier>[+-][0-9]{1,7})?",
    re.IGNORECASE,
)
DECIMAL_PATTERN = r"^[+-]?(?:[0-9]{1,30}(?:\.[0-9]{1,30})?|\.[0-9]{1,30})$"

Count = Annotated[int, Field(strict=True, ge=1, le=MAX_COUNT, description="Number of independent draws.")]
SafeInteger = Annotated[int, Field(strict=True, ge=-MAX_SAFE_INTEGER, le=MAX_SAFE_INTEGER)]
DecimalText = Annotated[str, Field(pattern=DECIMAL_PATTERN, description="Exact decimal string, such as '-1.25'.")]

server = MCPServer(
    "rng",
    title="Random Numbers and Dice",
    version="1.0.0",
    instructions=(
        "Use roll_dice, random_integer, or random_decimal when the user requests a random draw. "
        "Report the values returned by the tool. For another draw or a reroll, call the tool again. "
        "Integer and decimal bounds are inclusive. Pass decimal bounds as strings and specify "
        "decimal_places when the user requests a precision."
    ),
    subscriptions=False,
)
RANDOM_TOOL = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)


class DiceResult(TypedDict):
    notation: str
    rolls: list[int]
    modifier: int
    total: int


class IntegerResult(TypedDict):
    values: list[int]


class DecimalResult(TypedDict):
    decimal_places: int
    values: list[str]


def draw_integers(minimum: int, maximum: int, count: int) -> list[int]:
    if minimum > maximum:
        raise ToolError("The minimum must be less than or equal to the maximum.")
    return [minimum + secrets.randbelow(maximum - minimum + 1) for _ in range(count)]


@server.tool(title="Roll dice", annotations=RANDOM_TOOL)
def roll_dice(
    notation: Annotated[
        str, Field(min_length=2, max_length=19, description="Dice notation, such as d20, 2d6+3, or d%.")
    ] = "d6",
) -> DiceResult:
    """Roll fair dice. Return each face rolled and the total with the optional modifier applied once."""
    notation = notation.strip().lower()
    match = DICE_PATTERN.fullmatch(notation)
    if match is None:
        raise ToolError("Use dice notation such as d20, 2d6+3, or d%.")

    count = int(match["count"] or "1")
    sides = 100 if match["sides"] == "%" else int(match["sides"])
    modifier = int(match["modifier"] or "0")
    if not 1 <= count <= MAX_COUNT or not 2 <= sides <= MAX_SIDES:
        raise ToolError(f"Roll 1–{MAX_COUNT} dice with 2–{MAX_SIDES:,} sides each.")
    if abs(modifier) > MAX_SIDES:
        raise ToolError(f"The modifier must be between -{MAX_SIDES:,} and {MAX_SIDES:,}.")

    rolls = draw_integers(1, sides, count)
    return {"notation": notation, "rolls": rolls, "modifier": modifier, "total": sum(rolls) + modifier}


@server.tool(title="Draw random integers", annotations=RANDOM_TOOL)
def random_integer(minimum: SafeInteger, maximum: SafeInteger, count: Count = 1) -> IntegerResult:
    """Draw uniform random integers between the inclusive bounds. Repeated values are possible."""
    return {"values": draw_integers(minimum, maximum, count)}


@server.tool(title="Draw random decimals", annotations=RANDOM_TOOL)
def random_decimal(
    minimum: DecimalText,
    maximum: DecimalText,
    decimal_places: Annotated[int, Field(strict=True, ge=0, le=18)] = 6,
    count: Count = 1,
) -> DecimalResult:
    """Draw uniformly from exact decimals at the given precision inside the inclusive bounds.

    Send bounds as decimal strings. Results are fixed-point strings with trailing zeros preserved.
    """
    lower = Fraction(Decimal(minimum))
    upper = Fraction(Decimal(maximum))
    if lower > upper:
        raise ToolError("The minimum must be less than or equal to the maximum.")

    scale = 10**decimal_places
    first = ceil(lower * scale)
    last = floor(upper * scale)
    if first > last:
        raise ToolError("No values fit inside the bounds at this precision. Increase decimal_places or widen the range.")

    # Format the sampled integer on the decimal grid without binary floating point.
    values = []
    for value in draw_integers(first, last, count):
        digits = str(abs(value)).zfill(decimal_places + 1)
        if decimal_places:
            digits = f"{digits[:-decimal_places]}.{digits[-decimal_places:]}"
        values.append(f"-{digits}" if value < 0 else digits)
    return {"decimal_places": decimal_places, "values": values}


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Random Numbers and Dice MCP tools.")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8787, help="HTTP port (default: 8787).")
    parser.add_argument("--allowed-host", action="append", default=[], help="Additional allowed HTTP Host header.")
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run()
        return

    loopback_hosts = ["localhost", "127.0.0.1", "[::1]"]
    server.run(
        "streamable-http",
        host=args.host,
        port=args.port,
        json_response=True,
        stateless_http=True,
        max_request_body_size=16_384,
        transport_security=TransportSecuritySettings(
            allowed_hosts=loopback_hosts + [f"{host}:*" for host in loopback_hosts] + args.allowed_host,
            allowed_origins=[f"http://{host}:*" for host in loopback_hosts],
        ),
    )


if __name__ == "__main__":
    main()
