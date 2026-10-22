import json
import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


async def map_files_to_episodes(
    client: AsyncOpenAI,
    *,
    show_name: str,
    episodes_block: str,
    files_block: str,
    season_hint: int,
    num_files: int,
) -> dict[str, dict[str, int]] | None:
    """Ask the LLM to map video files to TV episodes.

    Returns a dict keyed by file-index string, each value ``{"season": int, "episode": int}``,
    or ``None`` on failure.
    """
    user_msg = (
        f"Show: {show_name}\n\n"
        f"Reference episodes list:\n{episodes_block}\n\n"
        f"Unreliable season hint: {season_hint}\n\n"
        f"Files:\n{files_block}"
    )

    model = "gpt-6-luna"

    response = await client.chat.completions.create(
        model=model,
        reasoning_effort="low",
        messages=[
            {
                "role": "system",
                "content": (
                    "Match each video file to its TV episode. "
                    "Do NOT assign by file order — read episode info from the filename.\n"
                    "Example number formats (in priority order):\n"
                    "1. Title match → if filename contains words from an episode title, prefer that over number guessing\n"
                    "2. 3-digit NNN where first digit < 5 → first digit=season, rest=episode (e.g. 112→s1e12, 306→s3e6)\n"
                    "3. Absolute number → match against (abs) numbers in the episode list\n"
                    "4. Plain episode number in filename (e.g. 'show 4 ...' → e=4)\n"
                    "5. Roman numerals I/II/III/IV → episode 1/2/3/4\n"
                    "Special cases:\n"
                    "- Multi-episode file (e.g. '1x01-02', 's04e01-02', '01-02. title'): use the FIRST episode number\n"
                    "- Part files (e.g. 'e01.part1', 'e01.part2', two audio cuts of same ep): map ALL parts to the same s+e\n"
                    "- Openings, trailers, bonuses, or files with no episode match: use s=0, e=0\n"
                    "- Season 0 is for specials/extras/OVA only — always prefer the hinted season over S00 "
                    "unless the file is explicitly a making-of, trailer, bonus feature, or OVA\n"
                    "IMPORTANT: every s+e pair (except 0+0) MUST exist in the provided episode list. "
                    "Do not invent episode numbers — if unsure, use s=0, e=0.\n"
                    "Output m keyed by file index string, each with s=season, e=episode. "
                    "Every file index must appear exactly once."
                ),
            },
            {"role": "user", "content": user_msg},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "episode_mapping",
                "strict": True,
                "schema": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "properties": {
                        "mapping": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "properties": {
                                    "season": {"type": "integer"},
                                    "episode": {"type": "integer"},
                                },
                                "required": ["season", "episode"],
                                "additionalProperties": False,
                            },
                            "required": [str(i) for i in range(num_files)],
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
    )

    content = response.choices[0].message.content or ""
    data = json.loads(content)
    data = data.get("episode_mapping", data)
    u = response.usage
    if u is not None:
        logger.debug(
            "LLM episode mapping: model=%s prompt=%d completion=%d total=%d",
            model,
            u.prompt_tokens,
            u.completion_tokens,
            u.total_tokens,
        )
    return data.get("mapping")
