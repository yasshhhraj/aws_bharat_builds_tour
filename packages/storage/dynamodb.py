"""Single-table DynamoDB implementation of the Manifest trace repository."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import os
import re
from typing import Any
from uuid import uuid4

from packages.domain.enums import AgentName, ApprovalStatus, EffectClass, EventType, RunStatus
from packages.domain.errors import (
    ApprovalNotFoundError,
    ApprovalPersistenceConflictError,
    EffectReceiptConflictError,
    LedgerAppendError,
    LedgerIdempotencyConflictError,
    LedgerTamperValidationError,
    StorageConfigurationError,
    StorageUnavailableError,
    TraceNotFoundError,
    TraceRevisionConflictError,
    TraceSequenceError,
)
from packages.domain.models import (
    ApprovalRecord,
    Decision,
    LedgerHead,
    TamperResult,
    TraceEvent,
    TrajectoryState,
    VerificationResult,
    utc_now,
)
from packages.ledger.canonical import (
    GENESIS_HASH,
    LEDGER_SCHEMA_VERSION,
    calculate_event_hash,
    event_description_fingerprint,
)
from packages.ledger.verifier import verify_chain

from .codec import (
    decode_approval_json,
    decode_decision_json,
    decode_effect_json,
    decode_event_json,
    decode_head_json,
    decode_replay_json,
    decode_state_json,
    encode_approval_json,
    encode_decision_json,
    encode_effect_json,
    encode_event_json,
    encode_head_json,
    encode_replay_json,
    encode_state_json,
)
from .keyspace import (
    approval_pointer_pk,
    approval_replay_sk,
    approval_sk,
    decision_sk,
    effect_sk,
    event_replay_sk,
    event_sk,
    namespace_approval_sk,
    namespace_pk,
    namespace_trace_sk,
    opaque_key_hash,
    trace_pk,
    validate_namespace,
)
from .models import EffectReceipt, ReplayKind, ReplayRecord, StoredTrace, TraceTransition


META_SK = "META"
HEAD_SK = "HEAD"
POINTER_SK = "POINTER"


def _s(value: str) -> dict[str, str]:
    return {"S": value}


def _n(value: int) -> dict[str, str]:
    return {"N": str(value)}


class DynamoDBTraceStore:
    """DynamoDB-backed trace store using optimistic revisions and transactions."""

    name = "dynamodb"

    def __init__(
        self,
        *,
        table_name: str | None = None,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        namespace: str | None = None,
        client: Any | None = None,
    ) -> None:
        deployment_mode = os.getenv("MANIFEST_DEPLOYMENT_MODE", "local").strip().lower()
        if deployment_mode not in {"local", "aws"}:
            raise StorageConfigurationError(
                "MANIFEST_DEPLOYMENT_MODE must be local or aws."
            )
        self.table_name = table_name or os.getenv("MANIFEST_DYNAMODB_TABLE", "manifest-local")
        configured_endpoint = endpoint_url or os.getenv("MANIFEST_DYNAMODB_ENDPOINT")
        if deployment_mode == "aws":
            if configured_endpoint:
                raise StorageConfigurationError(
                    "AWS deployment must not configure MANIFEST_DYNAMODB_ENDPOINT."
                )
            if os.getenv("AWS_ACCESS_KEY_ID") == "local" or os.getenv(
                "AWS_SECRET_ACCESS_KEY"
            ) == "local":
                raise StorageConfigurationError(
                    "AWS deployment must use its instance role, not local credentials."
                )
            self.endpoint_url = None
        else:
            self.endpoint_url = configured_endpoint or "http://127.0.0.1:18000"
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.namespace = validate_namespace(
            namespace or os.getenv("MANIFEST_DEMO_NAMESPACE", "local-demo")
        )
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,255}", self.table_name):
            raise StorageConfigurationError(
                "DynamoDB table name must use 3-255 safe table-name characters."
            )
        if client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise StorageConfigurationError(
                    "The DynamoDB backend requires the boto3 dependency."
                ) from exc
            client_args: dict[str, Any] = {
                "region_name": self.region_name,
                # Local acceptance can briefly contend with Cedar and repeated
                # evaluation writes. Keep requests bounded but tolerate normal
                # workstation scheduling jitter without adding retries.
                "config": Config(
                    connect_timeout=2,
                    read_timeout=5,
                    retries={"max_attempts": 1},
                ),
            }
            if self.endpoint_url:
                client_args.update(
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "local"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "local"),
                )
            client = boto3.client("dynamodb", **client_args)
        self.client = client

    def validate_startup(self) -> None:
        try:
            self.client.describe_table(TableName=self.table_name)
        except Exception as exc:
            raise StorageUnavailableError(
                f"DynamoDB table {self.table_name} is unavailable."
            ) from exc

    def create_run(self, state: TrajectoryState) -> StoredTrace:
        if state.events or state.next_sequence != 1:
            raise TraceSequenceError("A new trace must have no events.")
        state.storage_revision = 0
        now = utc_now()
        head = LedgerHead(
            trace_id=state.trace_id,
            sequence=0,
            event_count=0,
            event_hash=GENESIS_HASH,
            schema_version=LEDGER_SCHEMA_VERSION,
            updated_at=now,
        )
        actions = [
            self._put_action(self._trace_item(state.trace_id, META_SK, "trace", encode_state_json(state), Revision=0)),
            self._put_action(self._trace_item(state.trace_id, HEAD_SK, "head", encode_head_json(head))),
            self._put_action({
                "PK": _s(namespace_pk(self.namespace)),
                "SK": _s(namespace_trace_sk(state.trace_id)),
                "RecordType": _s("namespace_trace"),
                "TraceId": _s(state.trace_id),
            }),
        ]
        try:
            self.client.transact_write_items(TransactItems=actions)
        except Exception as exc:
            raise TraceSequenceError(f"Trace {state.trace_id} already exists.") from exc
        return StoredTrace(deepcopy(state), 0)

    def load_trace(self, trace_id: str, *, consistent: bool = True) -> StoredTrace:
        meta = self._get(trace_pk(trace_id), META_SK, consistent=consistent)
        if meta is None:
            raise TraceNotFoundError(f"Trace {trace_id} was not found.")
        events = tuple(self.get_events(trace_id))
        decisions = tuple(self.get_decisions(trace_id))
        state = decode_state_json(meta["Document"]["S"], events=events, decisions=decisions)
        revision = int(meta["Revision"]["N"])
        state.storage_revision = revision
        return StoredTrace(state, revision)

    def get_state(self, trace_id: str) -> TrajectoryState:
        return self.load_trace(trace_id).state

    def append_event(
        self,
        state: TrajectoryState,
        event_type: EventType,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        agent: AgentName | None = None,
        tool_name: str | None = None,
        effect_class: EffectClass | None = None,
        idempotency_key: str | None = None,
    ) -> TraceEvent:
        safe_details = deepcopy(details or {})
        fingerprint = None
        replay_key = None
        if idempotency_key is not None:
            fingerprint = event_description_fingerprint(
                trace_id=state.trace_id,
                event_type=event_type,
                summary=summary,
                details=safe_details,
                agent=agent,
                tool_name=tool_name,
                effect_class=effect_class,
                idempotency_key=idempotency_key,
            )
            replay_key = opaque_key_hash(idempotency_key)
            existing = self._get(trace_pk(state.trace_id), event_replay_sk(replay_key))
            if existing is not None:
                replay = decode_replay_json(existing["Document"]["S"])
                if replay.fingerprint != fingerprint:
                    raise LedgerIdempotencyConflictError(
                        "A ledger idempotency key was reused with different event fields."
                    )
                item = self._get(trace_pk(state.trace_id), event_sk(int(replay.result_reference)))
                if item is None:
                    raise LedgerAppendError("A ledger replay points to a missing event.")
                return decode_event_json(item["Document"]["S"])

        head = self.get_head(state.trace_id)
        sequence = head.sequence + 1
        if state.next_sequence != sequence:
            raise TraceSequenceError(
                f"Trace {state.trace_id} expected sequence {sequence}, received {state.next_sequence}."
            )
        now = utc_now()
        event = TraceEvent(
            event_id=f"EVT-{uuid4()}", trace_id=state.trace_id, sequence=sequence,
            event_type=event_type, summary=summary, details=safe_details,
            agent=agent, tool_name=tool_name, effect_class=effect_class,
            occurred_at=now, schema_version=LEDGER_SCHEMA_VERSION,
            previous_hash=head.event_hash, event_hash="", idempotency_key=idempotency_key,
        )
        event = replace(event, event_hash=calculate_event_hash(event))
        new_head = LedgerHead(
            trace_id=state.trace_id, sequence=sequence, event_count=head.event_count + 1,
            event_hash=event.event_hash, schema_version=LEDGER_SCHEMA_VERSION, updated_at=now,
        )
        old_revision = state.storage_revision
        state.events.append(event)
        state.next_sequence += 1
        state.storage_revision += 1
        actions = [
            self._put_action(self._trace_item(state.trace_id, event_sk(sequence), "event", encode_event_json(event))),
            {"Update": {
                "TableName": self.table_name,
                "Key": self._key(trace_pk(state.trace_id), HEAD_SK),
                "UpdateExpression": "SET #d = :d, #seq = :next",
                "ConditionExpression": "#seq = :expected",
                "ExpressionAttributeNames": {"#d": "Document", "#seq": "Sequence"},
                "ExpressionAttributeValues": {":d": _s(encode_head_json(new_head)), ":next": _n(sequence), ":expected": _n(head.sequence)},
            }},
            self._meta_update_action(state, old_revision),
        ]
        if replay_key and fingerprint:
            replay = ReplayRecord(state.trace_id, ReplayKind.EVENT, replay_key, fingerprint, str(sequence))
            actions.append(self._put_action(self._trace_item(state.trace_id, event_replay_sk(replay_key), "event_replay", encode_replay_json(replay))))
        try:
            self.client.transact_write_items(TransactItems=actions)
        except Exception as exc:
            state.events.pop()
            state.next_sequence -= 1
            state.storage_revision = old_revision
            raise TraceRevisionConflictError(f"Trace {state.trace_id} changed concurrently.") from exc
        return deepcopy(event)

    def append_decision(self, state: TrajectoryState, decision: Decision) -> None:
        old_revision = state.storage_revision
        state.decisions.append(decision)
        state.storage_revision += 1
        actions = [
            self._put_action(self._trace_item(state.trace_id, decision_sk(decision.created_at, decision.decision_id), "decision", encode_decision_json(decision))),
            self._meta_update_action(state, old_revision),
        ]
        try:
            self.client.transact_write_items(TransactItems=actions)
        except Exception as exc:
            state.decisions.pop()
            state.storage_revision = old_revision
            raise TraceRevisionConflictError(f"Trace {state.trace_id} changed concurrently.") from exc

    def get_events(self, trace_id: str) -> list[TraceEvent]:
        return [decode_event_json(item["Document"]["S"]) for item in self._query(trace_pk(trace_id), "EVENT#")]

    def get_decisions(self, trace_id: str) -> list[Decision]:
        return [decode_decision_json(item["Document"]["S"]) for item in self._query(trace_pk(trace_id), "DECISION#")]

    def get_head(self, trace_id: str) -> LedgerHead:
        item = self._get(trace_pk(trace_id), HEAD_SK)
        if item is None:
            if self._get(trace_pk(trace_id), META_SK) is None:
                raise TraceNotFoundError(f"Trace {trace_id} was not found.")
            raise LedgerAppendError(f"Trace {trace_id} has no ledger head.")
        return decode_head_json(item["Document"]["S"])

    def verify_trace(self, trace_id: str) -> VerificationResult:
        return verify_chain(trace_id, self.get_events(trace_id), self.get_head(trace_id))

    def add_approval(self, state: TrajectoryState, approval: ApprovalRecord) -> None:
        old_revision = state.storage_revision
        state.storage_revision += 1
        document = encode_approval_json(approval)
        common = {"RecordType": _s("approval"), "Document": _s(document), "Version": _n(approval.version), "TraceId": _s(approval.trace_id)}
        actions = [
            self._put_action({"PK": _s(trace_pk(state.trace_id)), "SK": _s(approval_sk(approval.approval_id)), **common}),
            self._put_action({"PK": _s(approval_pointer_pk(approval.approval_id)), "SK": _s(POINTER_SK), **common}),
            self._put_action({"PK": _s(namespace_pk(self.namespace)), "SK": _s(namespace_approval_sk(approval.created_at, approval.approval_id)), "ApprovalId": _s(approval.approval_id), **common}),
            self._meta_update_action(state, old_revision),
        ]
        try:
            self.client.transact_write_items(TransactItems=actions)
        except Exception as exc:
            state.storage_revision = old_revision
            raise ApprovalPersistenceConflictError("Approval could not be created.") from exc

    def get_approval(self, approval_id: str) -> ApprovalRecord:
        item = self._get(approval_pointer_pk(approval_id), POINTER_SK)
        if item is None:
            raise ApprovalNotFoundError(f"Approval {approval_id} was not found.")
        return decode_approval_json(item["Document"]["S"])

    def replace_approval(self, approval: ApprovalRecord) -> None:
        current = self.get_approval(approval.approval_id)
        expected = approval.version - 1
        if current.version != expected:
            raise ApprovalPersistenceConflictError("Approval version changed concurrently.")
        document = encode_approval_json(approval)
        namespace_sk = namespace_approval_sk(approval.created_at, approval.approval_id)
        keys = [
            self._key(trace_pk(approval.trace_id), approval_sk(approval.approval_id)),
            self._key(approval_pointer_pk(approval.approval_id), POINTER_SK),
            self._key(namespace_pk(self.namespace), namespace_sk),
        ]
        actions = [self._approval_update_action(key, document, approval.version, expected) for key in keys]
        try:
            self.client.transact_write_items(TransactItems=actions)
        except Exception as exc:
            raise ApprovalPersistenceConflictError("Approval version changed concurrently.") from exc

    def list_approvals(self, trace_id: str | None = None, status: ApprovalStatus | None = None) -> list[ApprovalRecord]:
        items = self._query(namespace_pk(self.namespace), "APPROVAL#")
        approvals = [decode_approval_json(item["Document"]["S"]) for item in items]
        if trace_id is not None:
            approvals = [item for item in approvals if item.trace_id == trace_id]
        if status is not None:
            approvals = [item for item in approvals if item.status == status]
        return sorted(approvals, key=lambda item: (item.created_at, item.approval_id))

    def get_approval_replay_fingerprint(self, approval_id: str, idempotency_key: str) -> str | None:
        approval = self.get_approval(approval_id)
        key_hash = opaque_key_hash(idempotency_key)
        item = self._get(trace_pk(approval.trace_id), approval_replay_sk(key_hash))
        if item is None:
            return None
        return decode_replay_json(item["Document"]["S"]).fingerprint

    def record_approval_replay(self, approval_id: str, idempotency_key: str, fingerprint: str) -> None:
        approval = self.get_approval(approval_id)
        key_hash = opaque_key_hash(idempotency_key)
        replay = ReplayRecord(approval.trace_id, ReplayKind.APPROVAL, key_hash, fingerprint, approval_id)
        item = self._trace_item(approval.trace_id, approval_replay_sk(key_hash), "approval_replay", encode_replay_json(replay))
        try:
            self.client.put_item(TableName=self.table_name, Item=item, ConditionExpression="attribute_not_exists(PK)")
        except Exception:
            existing = self.get_approval_replay_fingerprint(approval_id, idempotency_key)
            if existing != fingerprint:
                raise ApprovalPersistenceConflictError("Approval replay key conflict.")

    def get_effect_receipt(self, trace_id: str, key_hash: str) -> EffectReceipt | None:
        item = self._get(trace_pk(trace_id), effect_sk(key_hash))
        return decode_effect_json(item["Document"]["S"]) if item else None

    def put_effect_receipt(self, receipt: EffectReceipt) -> EffectReceipt:
        item = self._trace_item(receipt.trace_id, effect_sk(receipt.key_hash), "effect", encode_effect_json(receipt))
        try:
            self.client.put_item(TableName=self.table_name, Item=item, ConditionExpression="attribute_not_exists(PK)")
            return receipt
        except Exception:
            existing = self.get_effect_receipt(receipt.trace_id, receipt.key_hash)
            if existing is not None and existing.fingerprint == receipt.fingerprint:
                return existing
            raise EffectReceiptConflictError("An effect idempotency key conflict occurred.")

    def tamper_event_summary_for_demo(self, trace_id: str, sequence: int, replacement_summary: str) -> TamperResult:
        state = self.get_state(trace_id)
        terminal = bool(state.events) and state.events[-1].event_type in {EventType.RUN_COMPLETED, EventType.RUN_CANCELLED, EventType.RUN_FAILED}
        if state.status not in {RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.BLOCKED} and not terminal:
            raise LedgerTamperValidationError("Only a terminal disposable trace may be tampered with.")
        if not replacement_summary.strip():
            raise LedgerTamperValidationError("The replacement summary must not be empty.")
        item = self._get(trace_pk(trace_id), event_sk(sequence))
        if item is None:
            raise LedgerTamperValidationError(f"Trace {trace_id} has no event at sequence {sequence}.")
        event = replace(decode_event_json(item["Document"]["S"]), summary=replacement_summary)
        self.client.update_item(
            TableName=self.table_name, Key=self._key(trace_pk(trace_id), event_sk(sequence)),
            UpdateExpression="SET #d = :d", ExpressionAttributeNames={"#d": "Document"},
            ExpressionAttributeValues={":d": _s(encode_event_json(event))},
        )
        return TamperResult(trace_id=trace_id, sequence=sequence, field="summary")

    def commit_transition(self, transition: TraceTransition) -> StoredTrace:
        if transition.events or transition.decisions or transition.approval_upserts or transition.replay_records or transition.effect_receipts:
            raise StorageConfigurationError("Composite transitions are not used by the runtime adapter.")
        state = deepcopy(transition.state)
        state.storage_revision = transition.expected_revision + 1
        try:
            self.client.update_item(
                TableName=self.table_name, Key=self._key(trace_pk(transition.trace_id), META_SK),
                UpdateExpression="SET #d = :d, #r = :new", ConditionExpression="#r = :old",
                ExpressionAttributeNames={"#d": "Document", "#r": "Revision"},
                ExpressionAttributeValues={":d": _s(encode_state_json(state)), ":new": _n(state.storage_revision), ":old": _n(transition.expected_revision)},
            )
        except Exception as exc:
            raise TraceRevisionConflictError(f"Trace {transition.trace_id} changed concurrently.") from exc
        return StoredTrace(state, state.storage_revision)

    def reset_demo_namespace(self) -> int:
        pointers = self._query(namespace_pk(self.namespace), "")
        trace_ids = [item["TraceId"]["S"] for item in pointers if item.get("RecordType", {}).get("S") == "namespace_trace"]
        approval_ids = [item["ApprovalId"]["S"] for item in pointers if "ApprovalId" in item]
        delete_keys: list[dict[str, Any]] = []
        for trace_id in trace_ids:
            delete_keys.extend(self._key(item["PK"]["S"], item["SK"]["S"]) for item in self._query(trace_pk(trace_id), ""))
        delete_keys.extend(self._key(approval_pointer_pk(item), POINTER_SK) for item in approval_ids)
        delete_keys.extend(self._key(item["PK"]["S"], item["SK"]["S"]) for item in pointers)
        for offset in range(0, len(delete_keys), 25):
            requests = [{"DeleteRequest": {"Key": key}} for key in delete_keys[offset:offset + 25]]
            self.client.batch_write_item(RequestItems={self.table_name: requests})
        return len(trace_ids)

    def describe(self) -> dict[str, object]:
        return {
            "storage_backend": self.name,
            "storage_mode": "dynamodb_local" if self.endpoint_url else "dynamodb_aws",
            "consistent_reads": True,
            "table_name": self.table_name,
            "endpoint": self.endpoint_url,
            "namespace": self.namespace,
        }

    def _get(self, pk: str, sk: str, *, consistent: bool = True) -> dict[str, Any] | None:
        response = self.client.get_item(TableName=self.table_name, Key=self._key(pk, sk), ConsistentRead=consistent)
        return response.get("Item")

    def _query(self, pk: str, prefix: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        start = None
        while True:
            kwargs: dict[str, Any] = {
                "TableName": self.table_name,
                "KeyConditionExpression": (
                    "PK = :pk AND begins_with(SK, :prefix)" if prefix else "PK = :pk"
                ),
                "ExpressionAttributeValues": {":pk": _s(pk)},
                "ConsistentRead": True,
            }
            if prefix:
                kwargs["ExpressionAttributeValues"][":prefix"] = _s(prefix)
            if start:
                kwargs["ExclusiveStartKey"] = start
            response = self.client.query(**kwargs)
            items.extend(response.get("Items", []))
            start = response.get("LastEvaluatedKey")
            if not start:
                return items

    @staticmethod
    def _key(pk: str, sk: str) -> dict[str, dict[str, str]]:
        return {"PK": _s(pk), "SK": _s(sk)}

    def _trace_item(self, trace_id: str, sk: str, record_type: str, document: str, **numbers: int) -> dict[str, Any]:
        item: dict[str, Any] = {"PK": _s(trace_pk(trace_id)), "SK": _s(sk), "RecordType": _s(record_type), "TraceId": _s(trace_id), "Document": _s(document)}
        item.update({name: _n(value) for name, value in numbers.items()})
        if sk == HEAD_SK:
            item["Sequence"] = _n(0)
        return item

    def _put_action(self, item: dict[str, Any]) -> dict[str, Any]:
        return {"Put": {"TableName": self.table_name, "Item": item, "ConditionExpression": "attribute_not_exists(PK)"}}

    def _meta_update_action(self, state: TrajectoryState, old_revision: int) -> dict[str, Any]:
        return {"Update": {
            "TableName": self.table_name,
            "Key": self._key(trace_pk(state.trace_id), META_SK),
            "UpdateExpression": "SET #d = :d, #r = :new",
            "ConditionExpression": "#r = :old",
            "ExpressionAttributeNames": {"#d": "Document", "#r": "Revision"},
            "ExpressionAttributeValues": {":d": _s(encode_state_json(state)), ":new": _n(state.storage_revision), ":old": _n(old_revision)},
        }}

    def _approval_update_action(self, key: dict[str, Any], document: str, version: int, expected: int) -> dict[str, Any]:
        return {"Update": {
            "TableName": self.table_name, "Key": key,
            "UpdateExpression": "SET #d = :d, #v = :new",
            "ConditionExpression": "#v = :old",
            "ExpressionAttributeNames": {"#d": "Document", "#v": "Version"},
            "ExpressionAttributeValues": {":d": _s(document), ":new": _n(version), ":old": _n(expected)},
        }}
