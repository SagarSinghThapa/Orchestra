import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.core.checkpoints import PostgresSaver
from app.orchestrator.schemas import (
    IntentType,
    IntentClassificationResult,
    OrchestratorRequest,
    OrchestratorResponse,
)


@pytest.fixture
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Verify migration 004 attributes
    migration_path = Path(__file__).resolve().parent.parent.parent / "alembic" / "versions" / "004_add_checkpoints.py"
    spec = importlib.util.spec_from_file_location("migration_004", migration_path)
    migration_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_mod)
    assert migration_mod.revision == "004_add_checkpoints"
    assert migration_mod.down_revision == "003_add_documents"

    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE checkpoints (
                thread_id VARCHAR(255) NOT NULL,
                checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
                checkpoint_id VARCHAR(255) NOT NULL,
                parent_checkpoint_id VARCHAR(255),
                type VARCHAR(100),
                checkpoint TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE checkpoint_writes (
                thread_id VARCHAR(255) NOT NULL,
                checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
                checkpoint_id VARCHAR(255) NOT NULL,
                task_id VARCHAR(255) NOT NULL,
                idx INTEGER NOT NULL,
                channel VARCHAR(255) NOT NULL,
                type VARCHAR(100),
                value TEXT NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            );
            """
        ))
    return engine


class TestCheckpoints:
    def test_in_memory_saver_lifecycle(self):
        saver = PostgresSaver()
        config = {"configurable": {"thread_id": "proj_1_sess_10", "checkpoint_ns": ""}}
        checkpoint_data = {
            "v": 1,
            "ts": "2026-10-29T00:00:00Z",
            "id": "cp_001",
            "channel_values": {"step": "init", "count": 1},
        }
        metadata = {"source": "test"}

        # Put
        res_config = saver.put(config, checkpoint_data, metadata, {})
        assert res_config["configurable"]["checkpoint_id"] == "cp_001"

        # Get tuple
        cp_tuple = saver.get_tuple(config)
        assert cp_tuple is not None
        assert cp_tuple.checkpoint["id"] == "cp_001"
        assert cp_tuple.checkpoint["channel_values"]["step"] == "init"
        assert cp_tuple.checkpoint["channel_values"]["count"] == 1
        assert cp_tuple.metadata["source"] == "test"

    def test_database_backed_saver_lifecycle(self, sqlite_engine):
        saver = PostgresSaver(engine=sqlite_engine)
        thread_id = PostgresSaver.format_thread_id(project_id=42, session_id=101)
        assert thread_id == "proj_42_sess_101"

        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        cp1 = {
            "v": 1,
            "ts": "2026-10-29T00:00:01Z",
            "id": "1-0001",
            "channel_values": {"status": "started"},
        }
        saver.put(config, cp1, {"step": 1}, {})

        # Put writes
        write_config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": "1-0001"}}
        saver.put_writes(write_config, [("channel_a", {"event": "dispatched"})], task_id="task_1")

        # Second checkpoint
        config_step2 = {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": "1-0001"}}
        cp2 = {
            "v": 1,
            "ts": "2026-10-29T00:00:02Z",
            "id": "1-0002",
            "channel_values": {"status": "completed"},
        }
        saver.put(config_step2, cp2, {"step": 2}, {})

        # Load latest
        latest_tuple = saver.get_tuple(config)
        assert latest_tuple is not None
        assert latest_tuple.checkpoint["id"] == "1-0002"
        assert latest_tuple.checkpoint["channel_values"]["status"] == "completed"

        # Load specific checkpoint
        old_tuple = saver.get_tuple({"configurable": {"thread_id": thread_id, "checkpoint_id": "1-0001"}})
        assert old_tuple is not None
        assert old_tuple.checkpoint["id"] == "1-0001"
        assert old_tuple.checkpoint["channel_values"]["status"] == "started"
        assert len(old_tuple.pending_writes) == 1
        assert old_tuple.pending_writes[0][1] == "channel_a"
        assert old_tuple.pending_writes[0][2] == {"event": "dispatched"}

    def test_multi_tenant_thread_isolation(self, sqlite_engine):
        saver = PostgresSaver(engine=sqlite_engine)
        thread_a = PostgresSaver.format_thread_id(project_id=1, session_id=10)
        thread_b = PostgresSaver.format_thread_id(project_id=2, session_id=10)

        config_a = {"configurable": {"thread_id": thread_a, "checkpoint_ns": ""}}
        config_b = {"configurable": {"thread_id": thread_b, "checkpoint_ns": ""}}

        saver.put(config_a, {"v": 1, "id": "cp_a", "channel_values": {"secret": "project_1_data"}}, {}, {})
        saver.put(config_b, {"v": 1, "id": "cp_b", "channel_values": {"secret": "project_2_data"}}, {}, {})

        tuple_a = saver.get_tuple(config_a)
        tuple_b = saver.get_tuple(config_b)

        assert tuple_a is not None and tuple_b is not None
        assert tuple_a.checkpoint["channel_values"]["secret"] == "project_1_data"
        assert tuple_b.checkpoint["channel_values"]["secret"] == "project_2_data"

        # Attempt to access nonexistent thread in project 3
        tuple_c = saver.get_tuple({"configurable": {"thread_id": "proj_3_sess_10"}})
        assert tuple_c is None

    @pytest.mark.asyncio
    async def test_async_checkpoint_methods(self, sqlite_engine):
        saver = PostgresSaver(engine=sqlite_engine)
        thread_id = PostgresSaver.format_thread_id(project_id=5, session_id=99)
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        cp = {"v": 1, "id": "async_cp_1", "channel_values": {"async": True}}

        res = await saver.aput(config, cp, {"meta": "val"}, {})
        assert res["configurable"]["checkpoint_id"] == "async_cp_1"

        await saver.aput_writes(
            {"configurable": {"thread_id": thread_id, "checkpoint_id": "async_cp_1"}},
            [("chan", "val")],
            "task_async"
        )

        tuple_res = await saver.aget_tuple(config)
        assert tuple_res is not None
        assert tuple_res.checkpoint["channel_values"]["async"] is True


class TestOrchestratorSchemas:
    def test_orchestrator_request_valid(self):
        req = OrchestratorRequest(
            prompt="Analyze repository structure and cite relevant papers",
            session_id=12,
            forced_intent=IntentType.RESEARCH,
            research_params={"response_depth": "deep"}
        )
        assert req.prompt.startswith("Analyze repository")
        assert req.session_id == 12
        assert req.forced_intent == IntentType.RESEARCH
        assert req.research_params == {"response_depth": "deep"}

    def test_orchestrator_request_extra_forbid(self):
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            OrchestratorRequest(
                prompt="Hello world",
                unapproved_extra_field="malicious",
            )

    def test_orchestrator_request_bounds(self):
        with pytest.raises(ValueError):
            OrchestratorRequest(prompt="")  # min_length 1

        with pytest.raises(ValueError):
            OrchestratorRequest(prompt="a" * 4001)  # max_length 4000

    def test_intent_classification_result(self):
        result = IntentClassificationResult(
            intent=IntentType.DEVELOPER,
            confidence=0.95,
            rationale="Query asks for git diff and file refactoring"
        )
        assert result.intent == IntentType.DEVELOPER
        assert result.confidence == 0.95

    def test_orchestrator_response_contract(self):
        res = OrchestratorResponse(
            session_id=10,
            intent=IntentType.DIRECT_QA,
            answer="Here is the explanation...",
            execution_trace=["classified: direct_qa", "generated response"],
            metadata={"llm_calls_made": 1}
        )
        assert res.session_id == 10
        assert res.intent == IntentType.DIRECT_QA
        assert len(res.execution_trace) == 2
