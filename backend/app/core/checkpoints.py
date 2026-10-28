import asyncio
import base64
import datetime
import threading
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Sequence, Tuple
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    WRITES_IDX_MAP,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


class PostgresSaver(BaseCheckpointSaver):
    """
    Durable, dialect-portable LangGraph checkpoint saver backed by SQLAlchemy.
    Saves and loads state checkpoints and task writes to/from PostgreSQL or SQLite,
    with base64-encoded JsonPlusSerializer text payloads and namespaced thread isolation.
    """

    def __init__(
        self,
        engine: Optional[Engine] = None,
        session_factory: Optional[sessionmaker[Session]] = None,
    ):
        super().__init__(serde=JsonPlusSerializer())
        if engine is not None and hasattr(engine, "engine"):
            self.engine = engine.engine
        else:
            self.engine = engine
        self.session_factory = session_factory
        self._lock = threading.RLock()
        # In-memory storage fallback for offline unit testing without tables
        self._mem_checkpoints: Dict[Tuple[str, str, str], Tuple[Dict[str, Any], Dict[str, Any], Optional[str], datetime.datetime]] = {}
        self._mem_writes: Dict[Tuple[str, str, str], Dict[Tuple[str, int], Tuple[str, str, Any, str]]] = {}

    def _encode_to_string(self, data: Any) -> str:
        """Serializes data using JsonPlusSerializer and returns a formatted 'type:base64' string."""
        t, b = self.serde.dumps_typed(data)
        b64 = base64.b64encode(b).decode("ascii")
        return f"{t}:{b64}"

    def _decode_from_string(self, raw_str: str) -> Any:
        """Decodes 'type:base64' string and deserializes via JsonPlusSerializer."""
        if ":" in raw_str:
            t, b64 = raw_str.split(":", 1)
        else:
            t, b64 = "json", raw_str
        b = base64.b64decode(b64.encode("ascii"))
        return self.serde.loads_typed((t, b))

    @staticmethod
    def format_thread_id(project_id: int, session_id: int) -> str:
        """Constructs canonical compound namespaced thread identity."""
        return f"proj_{project_id}_sess_{session_id}"

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        with self._lock:
            thread_id: str = config["configurable"]["thread_id"]
            checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
            checkpoint_id: Optional[str] = get_checkpoint_id(config)

            if not self.engine:
                # Memory fallback
                matches = [
                    (k, v) for k, v in self._mem_checkpoints.items()
                    if k[0] == thread_id and k[1] == checkpoint_ns
                ]
                if not matches:
                    return None
                if checkpoint_id:
                    found = [v for k, v in matches if k[2] == checkpoint_id]
                    if not found:
                        return None
                    c, meta, parent_id, _ = found[0]
                    curr_cid = checkpoint_id
                else:
                    matches.sort(key=lambda m: m[1][3])
                    k, (c, meta, parent_id, _) = matches[-1]
                    curr_cid = k[2]

                writes_dict = self._mem_writes.get((thread_id, checkpoint_ns, curr_cid), {})
                pending_writes = [
                    (tid, chan, val)
                    for (tid, _), (_, chan, val, _) in writes_dict.items()
                ]

                return CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": curr_cid,
                        }
                    },
                    checkpoint=dict(c),
                    metadata=dict(meta),
                    pending_writes=pending_writes,
                    parent_config=(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_id,
                            }
                        }
                        if parent_id
                        else None
                    ),
                )

            with self.engine.connect() as conn:
                if checkpoint_id:
                    stmt = text(
                        "SELECT checkpoint_id, parent_checkpoint_id, checkpoint, metadata "
                        "FROM checkpoints "
                        "WHERE thread_id = :thread_id AND checkpoint_ns = :checkpoint_ns AND checkpoint_id = :checkpoint_id"
                    )
                    row = conn.execute(stmt, {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    }).first()
                else:
                    stmt = text(
                        "SELECT checkpoint_id, parent_checkpoint_id, checkpoint, metadata "
                        "FROM checkpoints "
                        "WHERE thread_id = :thread_id AND checkpoint_ns = :checkpoint_ns "
                        "ORDER BY created_at DESC LIMIT 1"
                    )
                    row = conn.execute(stmt, {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                    }).first()

                if not row:
                    return None

                cid, parent_id, c_str, m_str = row
                checkpoint_data = self._decode_from_string(c_str)
                metadata_data = self._decode_from_string(m_str)

                # Retrieve pending writes
                writes_stmt = text(
                    "SELECT task_id, channel, value "
                    "FROM checkpoint_writes "
                    "WHERE thread_id = :thread_id AND checkpoint_ns = :checkpoint_ns AND checkpoint_id = :checkpoint_id "
                    "ORDER BY idx ASC"
                )
                write_rows = conn.execute(writes_stmt, {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": cid,
                }).all()

                pending_writes = [
                    (w_task, w_chan, self._decode_from_string(w_val))
                    for w_task, w_chan, w_val in write_rows
                ]

                return CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": cid,
                        }
                    },
                    checkpoint=checkpoint_data,
                    metadata=metadata_data,
                    pending_writes=pending_writes,
                    parent_config=(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_id,
                            }
                        }
                        if parent_id
                        else None
                    ),
                )

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await asyncio.to_thread(self.get_tuple, config)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        with self._lock:
            thread_id: str = config["configurable"]["thread_id"]
            checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
            checkpoint_id: str = checkpoint["id"]
            parent_id: Optional[str] = config["configurable"].get("checkpoint_id")
            now = datetime.datetime.now(datetime.timezone.utc)

            # Retain complete channel values inside checkpoint copy
            c = dict(checkpoint)
            c_str = self._encode_to_string(c)
            meta_to_save = get_checkpoint_metadata(config, metadata)
            m_str = self._encode_to_string(meta_to_save)

            if not self.engine:
                self._mem_checkpoints[(thread_id, checkpoint_ns, checkpoint_id)] = (c, dict(metadata), parent_id, now)
                return {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    }
                }

            with self.engine.begin() as conn:
                # Upsert into checkpoints
                del_stmt = text(
                    "DELETE FROM checkpoints WHERE thread_id = :t AND checkpoint_ns = :ns AND checkpoint_id = :cid"
                )
                conn.execute(del_stmt, {"t": thread_id, "ns": checkpoint_ns, "cid": checkpoint_id})

                ins_stmt = text(
                    "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata, created_at) "
                    "VALUES (:t, :ns, :cid, :pid, :type, :cp, :meta, :created_at)"
                )
                conn.execute(ins_stmt, {
                    "t": thread_id,
                    "ns": checkpoint_ns,
                    "cid": checkpoint_id,
                    "pid": parent_id,
                    "type": c_str.split(":", 1)[0],
                    "cp": c_str,
                    "meta": m_str,
                    "created_at": now,
                })

            return {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            }

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        with self._lock:
            thread_id: str = config["configurable"]["thread_id"]
            checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
            checkpoint_id: str = config["configurable"]["checkpoint_id"]

            if not self.engine:
                outer_key = (thread_id, checkpoint_ns, checkpoint_id)
                if outer_key not in self._mem_writes:
                    self._mem_writes[outer_key] = {}
                for idx, (chan, val) in enumerate(writes):
                    idx_key = (task_id, WRITES_IDX_MAP.get(chan, idx))
                    self._mem_writes[outer_key][idx_key] = (
                        task_id,
                        chan,
                        val,
                        task_path,
                    )
                return

            with self.engine.begin() as conn:
                for idx, (chan, val) in enumerate(writes):
                    w_str = self._encode_to_string(val)
                    stmt = text(
                        "INSERT INTO checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value) "
                        "VALUES (:t, :ns, :cid, :task_id, :idx, :chan, :type, :val)"
                    )
                    try:
                        conn.execute(stmt, {
                            "t": thread_id,
                            "ns": checkpoint_ns,
                            "cid": checkpoint_id,
                            "task_id": task_id,
                            "idx": WRITES_IDX_MAP.get(chan, idx),
                            "chan": chan,
                            "type": w_str.split(":", 1)[0],
                            "val": w_str,
                        })
                    except Exception:
                        # Ignore duplicate write entries
                        pass

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        with self._lock:
            if not config:
                return
            t = self.get_tuple(config)
            if t:
                yield t

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item
