# RNG MCP

An MCP server that gives Codex, ChatGPT, and other MCP clients fair dice rolls, bounded integers, and fixed-precision decimals.

## Why use a random-number tool?

When a language model answers “roll a d20” by generating text, there's no guarantee that each face has a 1-in-20 chance or that successive rolls are independent. In a tabletop RPG, those odds matter. An attack roll, a saving throw, or a roll on a random encounter table should follow the game's probabilities even when the story seems to favor a particular outcome.

RNG MCP lets the assistant pass the dice notation or bounds to a separate tool. The server draws from the operating system's cryptographically secure random generator and returns the actual results. Each die face or allowed value has equal probability on each draw. Dice results include the individual faces and modifier so players can check the total. The server itself needs no API key and makes no outbound requests for draws. [Python's `secrets.randbelow` documentation](https://docs.python.org/3/library/secrets.html#secrets.randbelow)

### At the table

- **Attack roll** — “Use `rng` to roll `1d20+5`. Show the natural roll and the modified total.”
- **Advantage** — “Use `rng` to roll `2d20`. Show both faces and tell me which is higher.”
- **Encounter table** — “Use `rng` to draw an integer from 1 to 12 and tell me which row to use.”

## Tools

| Tool | Example arguments | Result |
| --- | --- | --- |
| `roll_dice` | `{"notation":"2d20+5"}` | Each roll, the modifier, and the total. Defaults to `d6`. Supports `d4`, `d6`, `d8`, `d10`, `d12`, `d20`, `d100`, percentile notation `d%`, and custom dice. |
| `random_integer` | `{"minimum":-10,"maximum":10,"count":3}` | Uniform integers within the inclusive bounds. Bounds can be anywhere from −9,007,199,254,740,991 to 9,007,199,254,740,991. |
| `random_decimal` | `{"minimum":"0.10","maximum":"0.20","decimal_places":2}` | Uniform exact decimals within the inclusive bounds, formatted as strings such as `"0.17"` to preserve precision and trailing zeros. |

Each call can roll up to 100 dice or draw up to 100 values. Dice can have 2 to 1,000,000 sides and a single signed modifier of up to 1,000,000 in magnitude. Number draws default to one value. Multiple draws are independent and can repeat.

Decimals use a grid at the requested precision. At two decimal places, the example above has 11 equally likely values, including both endpoints. Bounds between grid points are respected. For example, `"0.105"` through `"0.129"` allows `"0.11"` and `"0.12"` at two places. If the interval contains no grid points, the tool returns an error. Send bounds as plain decimal strings with up to 30 digits on either side of the decimal point. Output precision can be 0–18 places and defaults to 6.

## Set up locally

You’ll need uv and Python 3.12 or newer. [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

```sh
git clone https://github.com/Obscuretone/rng-mcp.git
cd rng-mcp
uv sync --locked
```

## Connect Codex

Run these commands from the cloned folder.

```sh
codex mcp add rng -- "$(command -v uv)" run --locked --directory "$PWD" python server.py
codex mcp list
```

Start a new Codex session. ChatGPT desktop shares the MCP configuration on the same Codex host. To set it up from desktop settings, add a **STDIO** server named `rng` with the absolute path to `uv` as its command. Use these arguments and replace the example directory with your clone's absolute path.

```text
run
--locked
--directory
/absolute/path/to/rng-mcp
python
server.py
```

Save and restart when prompted. [OpenAI documentation for Codex MCP setup](https://learn.chatgpt.com/docs/extend/mcp#connect-codex-to-an-mcp-server)

## Connect ChatGPT on the web

Run the server in Streamable HTTP mode.

```sh
uv run --locked python server.py --transport http
```

The listener is `http://127.0.0.1:8787/mcp`. Connect it through an [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), or forward it through a publicly reachable HTTPS endpoint. If your HTTPS proxy preserves the public Host header, add that hostname to the launch command with `--allowed-host rng.example.com`. The HTTP server itself has no authentication.

In ChatGPT Plugins, select **Add custom MCP server**. Choose **Tunnel** and select your tunnel, or enter your HTTPS URL ending in `/mcp`. Select **No authentication** for this server, create the plugin, and install it. In a new chat, type `@` and choose the plugin. Custom server access depends on your workspace settings. [ChatGPT Plugins](https://chatgpt.com/plugins) · [OpenAI documentation for connecting a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)
