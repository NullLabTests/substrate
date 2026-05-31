from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Sequence


class ShardStrategy(ABC):
    @abstractmethod
    def assign(self, agent_id: str) -> int:
        ...

    @abstractmethod
    def shard_count(self) -> int:
        ...

    @abstractmethod
    def agents_for_shard(self, agent_ids: Sequence[str], shard_id: int) -> list[str]:
        ...


class ConsistentHashShard(ShardStrategy):
    def __init__(self, num_shards: int, virtual_nodes: int = 100) -> None:
        if num_shards < 1:
            raise ValueError("num_shards must be >= 1")
        if virtual_nodes < 1:
            raise ValueError("virtual_nodes must be >= 1")
        self._num_shards = num_shards
        self._virtual_nodes = virtual_nodes
        self._ring: list[tuple[int, int]] = []
        self._build_ring()

    def _build_ring(self) -> None:
        points: list[tuple[int, int]] = []
        for shard_id in range(self._num_shards):
            for vnode in range(self._virtual_nodes):
                key = f"shard:{shard_id}:vnode:{vnode}"
                h = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
                points.append((h, shard_id))
        points.sort(key=lambda x: x[0])
        self._ring = points

    def assign(self, agent_id: str) -> int:
        h = int(hashlib.sha256(agent_id.encode()).hexdigest()[:16], 16)
        for hash_val, shard_id in self._ring:
            if h <= hash_val:
                return shard_id
        return self._ring[0][1]

    def shard_count(self) -> int:
        return self._num_shards

    def agents_for_shard(
        self, agent_ids: Sequence[str], shard_id: int
    ) -> list[str]:
        return [aid for aid in agent_ids if self.assign(aid) == shard_id]

    def rebalance(self, new_num_shards: int) -> None:
        self._num_shards = new_num_shards
        self._build_ring()

    def get_worker_for_agent(self, agent_id: str, worker_ids: list[str]) -> str:
        shard = self.assign(agent_id)
        return worker_ids[shard % len(worker_ids)]

    def shard_load(self, agent_ids: Sequence[str]) -> dict[int, int]:
        counts: dict[int, int] = {}
        for aid in agent_ids:
            s = self.assign(aid)
            counts[s] = counts.get(s, 0) + 1
        return counts


class RoundRobinShard(ShardStrategy):
    def __init__(self, num_shards: int) -> None:
        if num_shards < 1:
            raise ValueError("num_shards must be >= 1")
        self._num_shards = num_shards
        self._counter: int = 0

    def assign(self, agent_id: str) -> int:
        self._counter = (self._counter + 1) % self._num_shards
        return self._counter

    def shard_count(self) -> int:
        return self._num_shards

    def agents_for_shard(
        self, agent_ids: Sequence[str], shard_id: int
    ) -> list[str]:
        return [aid for i, aid in enumerate(agent_ids) if i % self._num_shards == shard_id]


AgentShard = ConsistentHashShard
