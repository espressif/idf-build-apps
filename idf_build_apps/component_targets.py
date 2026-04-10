import re
from typing import Iterable
from .constants import ALL_TARGETS

TARGET_PATTERN = re.compile(
    r"(?<![a-z0-9])("
    + "|".join(sorted(ALL_TARGETS, key=len, reverse=True))
    + r")(?![a-z0-9])"
)


def component_for_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2 or parts[0] != "components":
        return None
    return parts[1]


def component_root(component: str) -> str:
    return f"components/{component}"


def folder_for_path(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else path


def collapse_folders(folders: Iterable[str]) -> list[str]:
    collapsed: list[str] = []

    for folder in sorted(set(folders), key=lambda item: (item.count("/"), item)):
        if any(folder == root or folder.startswith(root + "/") for root in collapsed):
            continue
        collapsed.append(folder)

    return collapsed


def extract_targets(path: str) -> set[str]:
    return set(TARGET_PATTERN.findall(path))


def targets_for_folders(folders: list[str]) -> list[str]:
    found_targets: set[str] = set()

    for folder in folders:
        folder_targets = extract_targets(folder)
        if not folder_targets:
            return ["all"]
        found_targets.update(folder_targets)

    return sorted(found_targets)


def component_targets_from_files(
    modified_files: Iterable[str],
) -> dict[str, list[str]]:
    component_groups: dict[str, set[str]] = {}

    for path in modified_files:
        if not isinstance(path, str):
            continue

        path = path.strip()
        if not path:
            continue

        component = component_for_path(path)
        if component is None:
            continue

        folder = folder_for_path(path)
        root = component_root(component)
        if not folder.startswith(root):
            folder = root

        component_groups.setdefault(component, set()).add(folder)

    return {
        component: targets_for_folders(collapse_folders(component_folders))
        for component, component_folders in (
            (component, folders)
            for component, folders in sorted(component_groups.items())
        )
    }


def combined_targets_for_components(
    modified_files: Iterable[str],
    check_components: Iterable[str],
) -> list[str]:
    component_targets = component_targets_from_files(modified_files)
    combined_targets: set[str] = set()

    for component in check_components:
        targets = component_targets.get(component)
        if not targets:
            continue
        if targets == ["all"]:
            return ["all"]
        combined_targets.update(targets)

    return sorted(combined_targets)


def should_skip_build_for_components(
    modified_files: Iterable[str],
    check_components: Iterable[str],
    current_target: str,
) -> tuple[bool, list[str]]:
    targets = combined_targets_for_components(modified_files, check_components)
    should_skip = bool(targets) and "all" not in targets and current_target not in targets
    return should_skip, targets
