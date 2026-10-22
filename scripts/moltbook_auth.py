"""Read the Moltbook API key from the active Hermes profile only."""
import os

ENV_NAME = "MOLTBOOK_API_KEY"


def get_moltbook_api_key():
    """Return the configured API key, never logging it or reading legacy files."""
    key = os.environ.get(ENV_NAME, "").strip()
    if key:
        return key

    # Cron/CLI subprocesses can start with a stale environment after a profile
    # .env edit. HERMES_HOME identifies the active profile; do not guess another.
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if not hermes_home:
        return ""
    try:
        with open(os.path.join(hermes_home, ".env"), encoding="utf-8") as f:
            matches = []
            for line in f:
                name, sep, value = line.partition("=")
                if sep and name.strip() == ENV_NAME:
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                        value = value[1:-1]
                    matches.append(value)
    except OSError:
        return ""
    return matches[0] if len(matches) == 1 else ""
