from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from app.datasets.jpeg_integrity import (
    JpegIntegrityError,
    analyze_pair_geometry,
    perceptual_hamming_distance,
    read_jpeg_working_rgb,
    sha256_file,
)


SOURCE_GROUP_SCHEMA = "prographer.source-groups.v1"
NEAR_DUPLICATE_REVIEW_SCHEMA = "prographer.near-duplicate-reviews.v1"
SOURCE_GROUP_POLICY_VERSION = "sha256-phash16-geometry-v1"
DEFAULT_PHASH_DISTANCE = 16

SAME_SOURCE_GEOMETRY_ACTIONS = {
    "same_dimensions",
    "resize_only",
    "crop_same_ratio",
    "crop_or_geometry_mismatch",
    "rotation_mismatch",
    "mirror_mismatch",
}


@dataclass(frozen=True)
class SourceAsset:
    source_id: str
    event_id: str
    relative_path: str
    path: str
    sha256: str
    perceptual_hash64: str


@dataclass(frozen=True)
class SourceRelation:
    left_source_id: str
    right_source_id: str
    relation: str
    sha256_equal: bool
    phash_distance: int
    geometry_action: str | None
    geometry_inlier_ratio: float | None
    geometry_edge_similarity: float | None
    review_id: str | None
    review_decision: str | None


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}
        self.rank = {value: 0 for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


class _BKNode:
    def __init__(self, value: str, source_id: str) -> None:
        self.value = value
        self.source_ids = [source_id]
        self.children: dict[int, _BKNode] = {}


class _BKTree:
    def __init__(self) -> None:
        self.root: _BKNode | None = None

    def add(self, value: str, source_id: str) -> None:
        if self.root is None:
            self.root = _BKNode(value, source_id)
            return

        node = self.root
        while True:
            distance = perceptual_hamming_distance(value, node.value)
            if distance == 0:
                node.source_ids.append(source_id)
                return
            child = node.children.get(distance)
            if child is None:
                node.children[distance] = _BKNode(value, source_id)
                return
            node = child

    def query(self, value: str, radius: int) -> list[tuple[str, int]]:
        if self.root is None:
            return []

        found: list[tuple[str, int]] = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            distance = perceptual_hamming_distance(value, node.value)
            if distance <= radius:
                found.extend((source_id, distance) for source_id in node.source_ids)

            minimum = max(0, distance - radius)
            maximum = distance + radius
            for edge, child in node.children.items():
                if minimum <= edge <= maximum:
                    stack.append(child)

        return found


def source_asset_id(
    event_id: str,
    relative_path: str,
    source_sha256: str,
) -> str:
    payload = "|".join(
        (
            event_id.strip().casefold(),
            relative_path.replace("\\", "/").strip().casefold(),
            source_sha256,
        )
    )
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def _review_id(left_source_id: str, right_source_id: str) -> str:
    left, right = sorted((left_source_id, right_source_id))
    payload = f"near-duplicate-v1|{left}|{right}"
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def load_near_duplicate_reviews(
    path: Path | None,
    *,
    photographer_id: str,
) -> tuple[dict[str, dict], str | None]:
    if path is None:
        return {}, None

    review_path = path.expanduser().resolve(strict=True)
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    if payload.get("schema") != NEAR_DUPLICATE_REVIEW_SCHEMA:
        raise ValueError(
            "Unsupported near-duplicate review schema. Expected "
            f"{NEAR_DUPLICATE_REVIEW_SCHEMA!r}."
        )
    if str(payload.get("photographer_id") or "").strip() != photographer_id:
        raise ValueError(
            "near-duplicate reviews photographer_id does not match Intake photographer_id"
        )

    reviews: dict[str, dict] = {}
    for index, raw in enumerate(payload.get("reviews") or [], start=1):
        review_id = str(raw.get("review_id") or "").strip()
        decision = str(raw.get("decision") or "").strip()
        reviewed_by = str(raw.get("reviewed_by") or "").strip()
        reviewed_at = str(raw.get("reviewed_at") or "").strip()

        if not review_id:
            raise ValueError(f"near-duplicate review #{index} is missing review_id")
        if decision not in {"same_source", "distinct_source"}:
            raise ValueError(
                f"near-duplicate review #{index} has unsupported decision {decision!r}"
            )
        if not reviewed_by or not reviewed_at:
            raise ValueError(
                f"near-duplicate review #{index} requires reviewed_by and reviewed_at"
            )
        if review_id in reviews:
            raise ValueError(f"duplicate near-duplicate review id {review_id}")

        reviews[review_id] = {
            "review_id": review_id,
            "decision": decision,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "note": str(raw.get("note") or "").strip() or None,
        }

    return reviews, sha256_file(review_path)


def _group_id(member_source_ids: list[str]) -> str:
    payload = "source-group-v1|" + "|".join(sorted(member_source_ids))
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def build_source_groups(
    assets: list[SourceAsset],
    *,
    reviews: dict[str, dict] | None = None,
    phash_distance: int = DEFAULT_PHASH_DISTANCE,
) -> dict:
    reviews = reviews or {}
    assets_by_id = {asset.source_id: asset for asset in assets}
    if len(assets_by_id) != len(assets):
        raise ValueError("source asset ids must be unique")

    union = _UnionFind(assets_by_id)
    relations: list[SourceRelation] = []
    unresolved_suspects: list[dict] = []
    consumed_reviews: set[str] = set()

    by_sha: dict[str, list[SourceAsset]] = {}
    for asset in assets:
        by_sha.setdefault(asset.sha256, []).append(asset)

    for sha_value, group in sorted(by_sha.items()):
        ordered = sorted(group, key=lambda item: item.source_id)
        if len(ordered) <= 1:
            continue
        anchor = ordered[0]
        for other in ordered[1:]:
            union.union(anchor.source_id, other.source_id)
            relations.append(
                SourceRelation(
                    left_source_id=anchor.source_id,
                    right_source_id=other.source_id,
                    relation="exact_sha256",
                    sha256_equal=True,
                    phash_distance=perceptual_hamming_distance(
                        anchor.perceptual_hash64,
                        other.perceptual_hash64,
                    ),
                    geometry_action=None,
                    geometry_inlier_ratio=None,
                    geometry_edge_similarity=None,
                    review_id=None,
                    review_decision=None,
                )
            )

    tree = _BKTree()
    candidate_pairs: dict[tuple[str, str], int] = {}
    for asset in sorted(assets, key=lambda item: item.source_id):
        for other_source_id, distance in tree.query(
            asset.perceptual_hash64,
            phash_distance,
        ):
            left, right = sorted((asset.source_id, other_source_id))
            if assets_by_id[left].sha256 == assets_by_id[right].sha256:
                continue
            previous = candidate_pairs.get((left, right))
            if previous is None or distance < previous:
                candidate_pairs[(left, right)] = distance
        tree.add(asset.perceptual_hash64, asset.source_id)

    decoded_cache: dict[str, object] = {}

    def _rgb(asset: SourceAsset):
        cached = decoded_cache.get(asset.source_id)
        if cached is not None:
            return cached
        image, _ = read_jpeg_working_rgb(asset.path)
        decoded_cache[asset.source_id] = image
        return image

    for (left_id, right_id), distance in sorted(candidate_pairs.items()):
        left = assets_by_id[left_id]
        right = assets_by_id[right_id]
        review_id = _review_id(left_id, right_id)

        try:
            geometry = analyze_pair_geometry(
                _rgb(left),
                _rgb(right),
            )
            geometry_action = geometry.action
            inlier_ratio = geometry.inlier_ratio
            edge_similarity = geometry.edge_similarity
        except JpegIntegrityError:
            geometry = None
            geometry_action = "decode_error"
            inlier_ratio = None
            edge_similarity = None

        if geometry is not None and geometry.action in SAME_SOURCE_GEOMETRY_ACTIONS:
            union.union(left_id, right_id)
            relations.append(
                SourceRelation(
                    left_source_id=left_id,
                    right_source_id=right_id,
                    relation="verified_near_duplicate",
                    sha256_equal=False,
                    phash_distance=distance,
                    geometry_action=geometry_action,
                    geometry_inlier_ratio=inlier_ratio,
                    geometry_edge_similarity=edge_similarity,
                    review_id=None,
                    review_decision=None,
                )
            )
            continue

        review = reviews.get(review_id)
        if review is not None:
            consumed_reviews.add(review_id)
            if review["decision"] == "same_source":
                union.union(left_id, right_id)
            relations.append(
                SourceRelation(
                    left_source_id=left_id,
                    right_source_id=right_id,
                    relation="human_review",
                    sha256_equal=False,
                    phash_distance=distance,
                    geometry_action=geometry_action,
                    geometry_inlier_ratio=inlier_ratio,
                    geometry_edge_similarity=edge_similarity,
                    review_id=review_id,
                    review_decision=review["decision"],
                )
            )
            continue

        unresolved_suspects.append(
            {
                "review_id": review_id,
                "left": asdict(left),
                "right": asdict(right),
                "phash_distance": distance,
                "geometry_action": geometry_action,
                "geometry_inlier_ratio": inlier_ratio,
                "geometry_edge_similarity": edge_similarity,
                "required_decisions": ["same_source", "distinct_source"],
            }
        )

    unused_reviews = sorted(set(reviews) - consumed_reviews)
    if unused_reviews:
        raise ValueError(
            "Near-duplicate review is stale or no longer matches a current suspect: "
            + ", ".join(unused_reviews)
        )

    members_by_root: dict[str, list[SourceAsset]] = {}
    for asset in assets:
        members_by_root.setdefault(union.find(asset.source_id), []).append(asset)

    groups: list[dict] = []
    source_to_group: dict[str, str] = {}
    for members in members_by_root.values():
        ordered = sorted(members, key=lambda item: item.source_id)
        member_ids = [item.source_id for item in ordered]
        group_id = _group_id(member_ids)
        event_ids = sorted({item.event_id for item in ordered})
        groups.append(
            {
                "source_group_id": group_id,
                "event_ids": event_ids,
                "member_count": len(ordered),
                "members": [asdict(item) for item in ordered],
            }
        )
        for source_id in member_ids:
            source_to_group[source_id] = group_id

    groups.sort(key=lambda item: item["source_group_id"])
    unresolved_suspects.sort(key=lambda item: item["review_id"])

    return {
        "schema": SOURCE_GROUP_SCHEMA,
        "policy_version": SOURCE_GROUP_POLICY_VERSION,
        "phash_distance_threshold": int(phash_distance),
        "groups": groups,
        "relations": [asdict(item) for item in relations],
        "unresolved_suspects": unresolved_suspects,
        "source_to_group": source_to_group,
    }


def event_components_from_source_groups(
    eligible_event_ids: list[str],
    groups: list[dict],
) -> list[list[str]]:
    known = set(eligible_event_ids)
    union = _UnionFind(known)

    for group in groups:
        events = sorted(
            event_id
            for event_id in set(group.get("event_ids") or [])
            if event_id in known
        )
        if len(events) <= 1:
            continue
        anchor = events[0]
        for event_id in events[1:]:
            union.union(anchor, event_id)

    components: dict[str, list[str]] = {}
    for event_id in sorted(known):
        components.setdefault(union.find(event_id), []).append(event_id)

    return sorted(
        (sorted(values) for values in components.values()),
        key=lambda values: tuple(values),
    )
