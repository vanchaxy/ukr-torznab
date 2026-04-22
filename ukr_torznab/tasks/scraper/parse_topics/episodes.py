import re
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI

from ukr_torznab.clients.llm import map_files_to_episodes


def match_episodes(
    video_files: list[Path],
    skyhook: dict,
    season: int,
) -> tuple[dict[str, tuple[int, int]], bool] | None:
    season_episodes = _get_season_episodes(skyhook, season)
    if not season_episodes:
        return None

    file_nums = _extract_sxxexx(video_files) or _extract_positional(video_files)
    if file_nums is None:
        return None

    match_type = _numbers_match_season(file_nums, season_episodes)
    if match_type is None:
        return None

    if match_type == "absolute":
        abs_to_ep = {
            ep["absolute"]: ep["episode"] for ep in season_episodes if ep["absolute"] is not None
        }
        episode_map = {f: (season, abs_to_ep[num]) for f, num in file_nums.items()}
    else:
        episode_map = {f: (season, num) for f, num in file_nums.items()}

    expected = {ep["episode"] for ep in season_episodes}
    matched = {ep for _, ep in episode_map.values()}

    return episode_map, matched == expected


async def match_episodes_llm(
    video_files: list[Path],
    skyhook: dict,
    season: int,
    client: AsyncOpenAI,
) -> tuple[dict[str, tuple[int, int]], bool, int] | None:
    show_name = skyhook.get("title", "")

    expected_keys = [str(i) for i in range(len(video_files))]

    # Build compact episode list for all seasons
    seen: set[tuple[int, int]] = set()
    ep_lines: list[str] = []
    for ep in skyhook.get("episodes", []):
        s, e = ep["seasonNumber"], ep["episodeNumber"]
        if (s, e) in seen:
            continue
        seen.add((s, e))
        abs_num = ep.get("absoluteEpisodeNumber")
        title = ep.get("title", "")
        abs_part = f"({abs_num})" if abs_num is not None else ""
        ep_lines.append(f"S{s:02d}E{e:02d}{abs_part} {title}")

    files_block = "\n".join(f"{i} | {f.name}" for i, f in enumerate(video_files))
    episodes_block = "\n".join(ep_lines)

    mappings = await map_files_to_episodes(
        client,
        show_name=show_name,
        episodes_block=episodes_block,
        files_block=files_block,
        season_hint=season,
        num_files=len(video_files),
    )
    if not mappings:
        return None

    valid_se: set[tuple[int, int]] = {
        (ep["seasonNumber"], ep["episodeNumber"]) for ep in skyhook.get("episodes", [])
    }

    episode_map: dict[str, tuple[int, int]] = {}
    for key, val in mappings.items():
        se = (val["season"], val["episode"])
        if se == (0, 0) or key not in expected_keys:
            continue
        if se not in valid_se:
            continue
        episode_map[str(video_files[int(key)])] = se

    if not episode_map:
        return None

    season_counts: Counter = Counter(s for s, _ in episode_map.values())
    detected_season = season_counts.most_common(1)[0][0]

    season_episodes = _get_season_episodes(skyhook, detected_season)
    expected = {ep["episode"] for ep in season_episodes}
    matched = {ep for s, ep in episode_map.values() if s == detected_season}
    return episode_map, matched == expected, detected_season


def _get_season_episodes(skyhook: dict, season: int) -> list[dict]:
    episodes: list[dict] = []
    seen: set[tuple] = set()
    for ep in skyhook.get("episodes", []):
        key = (ep["episodeNumber"], ep["seasonNumber"], ep.get("absoluteEpisodeNumber"))
        if key not in seen and ep["seasonNumber"] == season:
            seen.add(key)
            episodes.append(
                {
                    "episode": ep["episodeNumber"],
                    "absolute": ep.get("absoluteEpisodeNumber"),
                },
            )
    return episodes


def _extract_sxxexx(files: list[Path]) -> dict[str, int] | None:
    results: dict[str, int] = {}
    for f in files:
        matches = re.findall(r"s\d+e(\d+)", str(f), re.IGNORECASE)
        if matches:
            results[str(f)] = int(matches[0])
    if len(results) == len(files) and len(set(results.values())) == len(files):
        return results
    return None


def _extract_positional(files: list[Path]) -> dict[str, int] | None:
    if len(files) <= 1:
        return None
    all_nums = [re.findall(r"\d+", str(f)) for f in files]
    if len(set(len(nums) for nums in all_nums)) != 1:
        return None
    for col in range(len(all_nums[0])):
        vals = [int(nums[col]) for nums in all_nums]
        if len(set(vals)) == len(files):
            return {str(f): int(nums[col]) for f, nums in zip(files, all_nums)}
    return None


def _numbers_match_season(
    file_nums: dict[str, int],
    season_episodes: list[dict],
) -> str | None:
    nums = set(file_nums.values())
    regular = {ep["episode"] for ep in season_episodes}
    absolute = {ep["absolute"] for ep in season_episodes if ep["absolute"] is not None}
    if nums.issubset(regular):
        return "episode"
    if nums.issubset(absolute):
        return "absolute"
    return None
