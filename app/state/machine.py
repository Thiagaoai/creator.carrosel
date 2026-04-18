"""StateMachine — transitions-lib FSM backed by Redis persistence (SDD §2.3)."""

from __future__ import annotations

from typing import Any

from transitions import Machine

from app.config import settings
from app.integrations.supabase_client import insert_flow, sync_flow_snapshot_to_supabase
from app.state import redis_store
from app.state.transitions import STATES, TERMINAL_STATES, TRANSITIONS
from app.utils.logging import get_logger

logger = get_logger(__name__)


class FlowModel:
    """Model class required by the transitions library.

    Holds the current state string; persistence is handled separately via Redis.
    """

    state: str


class StateMachine:
    """Manages the lifecycle of a single carousel flow.

    Creates a transitions.Machine instance per flow, restores it from Redis,
    and persists state after every transition.
    """

    def __init__(self, flow_id: str, initial_state: str = "INIT") -> None:
        self.flow_id = flow_id
        self._model = FlowModel()
        self._model.state = initial_state
        self._machine = Machine(
            model=self._model,
            states=STATES,
            transitions=TRANSITIONS,
            initial=initial_state,
            ignore_invalid_triggers=False,
        )

    @property
    def state(self) -> str:
        """Current state of the flow."""
        return str(self._model.state)

    def can_trigger(self, trigger: str) -> bool:
        """Return True if the given trigger is valid from the current state."""
        return self._machine.get_triggers(self._model.state).__contains__(trigger)

    def trigger(self, trigger: str) -> None:
        """Fire a transition trigger.

        Raises MachineError (from transitions) if the trigger is invalid.
        """
        logger.info(
            "fsm_transition",
            flow_id=self.flow_id,
            trigger=trigger,
            from_state=self.state,
        )
        getattr(self._model, trigger)()
        logger.info("fsm_transitioned", flow_id=self.flow_id, to_state=self.state)

    def is_terminal(self) -> bool:
        """Return True if the flow is in a terminal state."""
        return self.state in TERMINAL_STATES


# ── High-level async helpers ──────────────────────────────────────────────────

async def start_flow(
    telegram_user_id: int,
    brand: str,
) -> str:
    """Create a new flow, persist it, and return the flow_id."""
    flow_id = redis_store.new_flow_id()
    data: dict[str, Any] = {
        "flow_id": flow_id,
        "telegram_user_id": telegram_user_id,
        "brand": brand,
        "stage": "INIT",
    }
    await redis_store.save_flow(flow_id, data)
    await redis_store.set_user_active_flow(telegram_user_id, flow_id)

    if settings.supabase_url and settings.supabase_service_key:
        try:
            insert_flow(flow_id, telegram_user_id, brand, stage="INIT")
        except Exception as exc:
            logger.warning(
                "insert_flow_failed",
                flow_id=flow_id,
                error=str(exc),
            )
    sync_flow_snapshot_to_supabase(flow_id, data)

    logger.info("flow_started", flow_id=flow_id, user_id=telegram_user_id, brand=brand)
    return flow_id


async def load_machine(flow_id: str) -> tuple[StateMachine, dict[str, Any]]:
    """Load a StateMachine from Redis state. Raises KeyError if not found."""
    data = await redis_store.load_flow(flow_id)
    if data is None:
        raise KeyError(f"Flow {flow_id} not found in Redis")
    state = str(data.get("stage", "INIT"))
    return StateMachine(flow_id, initial_state=state), data


async def transition(
    flow_id: str,
    trigger: str,
    updates: dict[str, Any] | None = None,
) -> StateMachine:
    """Atomically acquire lock, fire trigger, persist new state, release lock.

    Args:
        flow_id: The flow to transition.
        trigger: The transition trigger name (e.g. "select_topic").
        updates: Optional additional fields to merge into the persisted flow data.

    Returns:
        The StateMachine after the transition.

    Raises:
        RuntimeError: If the lock cannot be acquired.
        KeyError: If the flow does not exist in Redis.
    """
    if not await redis_store.acquire_lock(flow_id):
        raise RuntimeError(f"Could not acquire lock for flow {flow_id}")

    try:
        machine, data = await load_machine(flow_id)
        machine.trigger(trigger)

        data["stage"] = machine.state
        if updates:
            data.update(updates)

        ttl = None
        if machine.is_terminal():
            ttl = settings.flow_ttl_terminal

        await redis_store.save_flow(flow_id, data, ttl=ttl)
        sync_flow_snapshot_to_supabase(flow_id, data)
        return machine
    finally:
        await redis_store.release_lock(flow_id)
