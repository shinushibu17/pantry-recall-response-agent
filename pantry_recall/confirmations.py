"""Human CLI boundary. Never register this operation as a model tool.

This local replay records a person's assertion, not independent observation or
authenticated identity. All inventory and confirmations in this prototype are synthetic.
"""

from dataclasses import asdict, dataclass
import json

from .store import Store, WorkflowError, encoded, now


@dataclass(frozen=True)
class HoldConfirmation:
    confirmation_id: str
    task_id: str
    inventory_id: str
    inventory_version: str
    recall_version: str
    quantity: int
    unit: str
    actor: str
    note: str
    attest_isolated: bool = False


def record_human_confirmation(store: Store, confirmation: HoldConfirmation, *, channel="human_confirmation_cli") -> dict:
    """Atomically apply an explicitly attested quantity, or return an identical receipt."""
    payload = asdict(confirmation)
    try:
        for field in ("confirmation_id", "task_id", "inventory_id", "inventory_version", "recall_version", "unit", "actor", "note"):
            if not isinstance(payload[field], str) or not payload[field].strip():
                raise WorkflowError("REQUIRED_CONFIRMATION_FIELD", f"{field} must be nonempty text")
        if confirmation.attest_isolated is not True:
            raise WorkflowError("ATTESTATION_REQUIRED", "Explicitly attest that this quantity has been isolated in the synthetic replay")
        if type(confirmation.quantity) is not int or confirmation.quantity <= 0:
            raise WorkflowError("INVALID_QUANTITY", "Quantity must be a positive integer")
        with store.transaction() as connection:
            prior = connection.execute("SELECT * FROM confirmations WHERE confirmation_id=?", (confirmation.confirmation_id,)).fetchone()
            if prior:
                if prior["payload"] != encoded(payload):
                    raise WorkflowError("CONFIRMATION_ID_CONFLICT", "This confirmation ID already records different evidence")
                return json.loads(prior["receipt"])

            case = store._case_row(connection, confirmation.inventory_id)
            task = connection.execute("SELECT * FROM tasks WHERE task_id=?", (confirmation.task_id,)).fetchone()
            if task is None:
                raise WorkflowError("UNKNOWN_TASK", "Task does not exist")
            if task["case_id"] != case["case_id"]:
                raise WorkflowError("WRONG_STOCK_GROUP", "Task belongs to a different stock group")
            if confirmation.recall_version != case["recall_version"] or confirmation.recall_version != task["recall_version"]:
                raise WorkflowError("STALE_RECALL_VERSION", "Confirmation must name the task's current recall version")
            if confirmation.inventory_version != case["inventory_version"] or confirmation.inventory_version != task["inventory_version"]:
                raise WorkflowError("STALE_INVENTORY_VERSION", "Confirmation must name the task's current stock evidence version")
            if task["type"] != "PERFORM_ACTION" or case["identification_state"] != "AFFECTED":
                raise WorkflowError("INVALID_TRANSITION", "Only an affected stock group's hold task can receive this confirmation")
            if task["status"] != "OPEN":
                raise WorkflowError("TASK_NOT_OPEN", "Only an open hold task can receive a new confirmation")
            if confirmation.unit != task["unit"]:
                raise WorkflowError("WRONG_UNIT", "Confirmation unit must match the task")
            remaining = task["quantity"] - task["confirmed_quantity"]
            if confirmation.quantity > remaining:
                raise WorkflowError("EXCESS_QUANTITY", "Confirmation quantity exceeds the unconfirmed remainder")

            total = task["confirmed_quantity"] + confirmation.quantity
            status = "DONE" if total == task["quantity"] else "OPEN"
            action_state = "COMPLETED_CONFIRMED" if status == "DONE" else "AWAITING_CONFIRMATION"
            receipt = {**payload, "confirmed_at": now(), "simulated": True,
                       "channel": channel, "action": "hold/isolation",
                       "location": task["location"], "confirmed_quantity": total,
                       "remaining_quantity": task["quantity"] - total, "task_status": status,
                       "identification_state": case["identification_state"], "action_state": action_state,
                       "basis": "authored pantry policy", "evidence_refs": json.loads(task["details"])["evidence_refs"],
                       "row_sha256": case["row_sha256"],
                       "scope": "This quantity's hold task only; no disposal, release, or completion of other recall obligations."}
            connection.execute("UPDATE tasks SET confirmed_quantity=?,status=? WHERE task_id=?", (total, status, task["task_id"]))
            connection.execute("UPDATE cases SET action_state=? WHERE case_id=?", (action_state, case["case_id"]))
            receipt["event_sequence"] = store._event(connection, "HOLD_CONFIRMED", receipt, case["case_id"], confirmation.actor, channel)
            connection.execute("INSERT INTO confirmations VALUES (?,?,?,?)", (confirmation.confirmation_id, task["task_id"], encoded(payload), encoded(receipt)))
            return receipt
    except WorkflowError as error:
        store.reject(error, "confirm_hold", confirmation.inventory_id, confirmation.actor)
        raise
