"""Offline reward and trusted-wall-clock policy for local campaigns."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from math import floor
from time import monotonic
from typing import Callable, Protocol
from uuid import uuid4

from sqlalchemy import select

from app.core.game_balance import OFFLINE_CAP_SECONDS, OFFLINE_MINIMUM_SECONDS
from app.database.connection import SessionLocal
from app.models import CampaignMetadata, Guild, OfflineReturnReport
from app.repositories.guild_repository import get_resources_by_guild_id
from app.services.offline_progress_service import (
    calculate_offline_material_rewards,
    gold_reward_sources,
    get_passive_gold_rate,
)
from app.services.gathering_service import advance_all_assignments


class ClockAnchorError(RuntimeError):
    """The external trusted-clock checkpoint could not be read or written."""


class AnchorProtector(Protocol):
    def protect(self, value: bytes) -> bytes: ...
    def unprotect(self, value: bytes) -> bytes: ...


class DpapiProtector:
    """Protect the campaign clock checkpoint using the current Windows user."""

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    @classmethod
    def _transform(cls, value: bytes, decrypt: bool) -> bytes:
        if os.name != "nt":
            raise ClockAnchorError("A proteção de horário só está disponível no Windows.")
        input_buffer = ctypes.create_string_buffer(value)
        input_blob = cls._Blob(len(value), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)))
        output_blob = cls._Blob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        if decrypt:
            ok = crypt32.CryptUnprotectData(
                ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
            )
        else:
            description = ctypes.c_wchar_p("Guild Idle Manager clock guard")
            ok = crypt32.CryptProtectData(
                ctypes.byref(input_blob), description, None, None, None, 0, ctypes.byref(output_blob)
            )
        if not ok:
            raise ClockAnchorError("Não foi possível verificar a proteção local de horário do aplicativo.")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)

    def protect(self, value: bytes) -> bytes:
        return self._transform(value, decrypt=False)

    def unprotect(self, value: bytes) -> bytes:
        return self._transform(value, decrypt=True)


class MemoryAnchorStore:
    """In-memory store used by deterministic clock tests."""

    def __init__(self):
        self.values: dict[str, dict[str, str]] = {}

    def load(self, campaign_id: str) -> dict[str, str] | None:
        value = self.values.get(campaign_id)
        return dict(value) if value else None

    def save(self, campaign_id: str, high_water_utc: datetime) -> None:
        self.values[campaign_id] = {
            "campaign_id": campaign_id,
            "high_water_utc": high_water_utc.astimezone(timezone.utc).isoformat(),
        }


class DpapiAnchorStore:
    def __init__(self, directory: str | Path, protector: AnchorProtector | None = None):
        self.directory = Path(directory)
        self.protector = protector or DpapiProtector()

    def _path(self, campaign_id: str) -> Path:
        return self.directory / f"{campaign_id}.clock"

    def load(self, campaign_id: str) -> dict[str, str] | None:
        path = self._path(campaign_id)
        if not path.exists():
            return None
        try:
            value = json.loads(self.protector.unprotect(path.read_bytes()).decode("utf-8"))
            if value.get("campaign_id") != campaign_id or not value.get("high_water_utc"):
                raise ValueError("campaign binding mismatch")
            datetime.fromisoformat(value["high_water_utc"])
            return value
        except Exception as exc:
            raise ClockAnchorError("A referência de horário da campanha está ausente ou corrompida.") from exc

    def save(self, campaign_id: str, high_water_utc: datetime) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        value = json.dumps(
            {"campaign_id": campaign_id, "high_water_utc": high_water_utc.astimezone(timezone.utc).isoformat()},
            separators=(",", ":"),
        ).encode("utf-8")
        path = self._path(campaign_id)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_bytes(self.protector.protect(value))
        temp_path.replace(path)


def default_anchor_store() -> DpapiAnchorStore:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise ClockAnchorError("A pasta de dados local não está disponível para verificar o horário da campanha.")
    return DpapiAnchorStore(Path(local_app_data) / "GuildIdleManager" / "clock-guard")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ClockDecision:
    elapsed_seconds: int = 0
    credited_seconds: int = 0
    stamina_seconds: int = 0
    warning: str | None = None


class ClockGuard:
    def __init__(
        self,
        anchor_store: DpapiAnchorStore | MemoryAnchorStore | None = None,
        wall_clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], float] | None = None,
    ):
        self.anchor_store = anchor_store or default_anchor_store()
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.monotonic_clock = monotonic_clock or monotonic
        self._session_started: dict[str, float] = {}

    def evaluate_return(
        self,
        campaign_id: str,
        session_state: str,
        closed_at_utc: datetime | None,
        now_utc: datetime | None = None,
        stamina_seconds: int = OFFLINE_CAP_SECONDS,
    ) -> ClockDecision:
        now = _as_utc(now_utc or self.wall_clock())
        if session_state in {"created", "initializing", "suspended", "closed"}:
            return ClockDecision()
        if session_state != "offline" or closed_at_utc is None:
            return ClockDecision(warning="A sessão anterior não foi encerrada corretamente; o progresso retroativo foi ignorado.")
        try:
            anchor = self.anchor_store.load(campaign_id)
        except ClockAnchorError:
            return ClockDecision(warning="A referência de horário da campanha está corrompida; nenhum progresso retroativo foi concedido.")
        if anchor is None:
            return ClockDecision(warning="A referência de horário da campanha não foi encontrada; nenhum progresso retroativo foi concedido.")
        try:
            high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"]))
        except (KeyError, ValueError, TypeError):
            return ClockDecision(warning="A referência de horário da campanha é inválida; nenhum progresso retroativo foi concedido.")
        closed_at = _as_utc(closed_at_utc)
        if now < high_water or now < closed_at:
            return ClockDecision(warning="O relógio voltou para antes do último horário confiável; o progresso foi pausado.")
        interval_start = max(closed_at, high_water)
        elapsed = max(0, floor((now - interval_start).total_seconds()))
        if elapsed < OFFLINE_MINIMUM_SECONDS:
            return ClockDecision(elapsed_seconds=elapsed)
        credited = min(elapsed, OFFLINE_CAP_SECONDS, max(0, stamina_seconds))
        return ClockDecision(
            elapsed_seconds=elapsed,
            credited_seconds=credited,
            stamina_seconds=credited,
            warning=(
                "O progresso offline foi limitado ao máximo permitido."
                if elapsed > OFFLINE_CAP_SECONDS
                else "O progresso offline foi limitado pela estamina disponível."
                if credited < min(elapsed, OFFLINE_CAP_SECONDS)
                else None
            ),
        )

    def activate_campaign(self, campaign_id: str) -> dict[str, object] | None:
        now = _as_utc(self.wall_clock())
        with SessionLocal() as db:
            metadata = db.get(CampaignMetadata, campaign_id)
            guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign_id))
            if metadata is None or guild is None:
                raise ValueError("A campanha não contém dados válidos de uma guilda para abrir.")
            previous_state = metadata.last_session_state
            closed_at = metadata.last_clean_shutdown_utc
            decision = self.evaluate_return(campaign_id, previous_state, closed_at, now, metadata.stamina_seconds)
            resources = get_resources_by_guild_id(db, guild.id)
            summary: dict[str, object] | None = None
            gathering = advance_all_assignments(
                db, guild, now=now, max_seconds=decision.credited_seconds,
            )
            regional_context = None
            if decision.elapsed_seconds >= OFFLINE_MINIMUM_SECONDS and not metadata.pending_offline_report:
                from app.models.regional import RegionalWorldState
                from app.services.regional_cycle_service import REGIONS, get_regional_board

                world_before = db.get(RegionalWorldState, campaign_id)
                completed_before = world_before.last_completed_cycle if world_before is not None else -1
                regional = get_regional_board(db, metadata, guild, now)
                cycles_processed = max(0, regional["world"].last_completed_cycle - completed_before)
                region_names = dict(REGIONS)
                recent_events = []
                for event in regional.get("event_history", [])[:3]:
                    try:
                        event_result = json.loads(event.summary_json or "{}").get("result")
                    except (TypeError, ValueError):
                        event_result = None
                    recent_events.append({
                        "type": event.event_type,
                        "region_code": event.region_code,
                        "region_name": region_names.get(event.region_code, event.region_code),
                        "status": event.status,
                        "status_label": {
                            "active": "Aberto", "in_progress": "Em andamento",
                            "resolved": "Concluído", "expired": "Expirado",
                            "suppressed": "Suprimido", "not_triggered": "Não ocorreu",
                        }.get(event.status, "Registrado"),
                        "result": event_result,
                    })
                regional_context = {
                    "cycles_processed": cycles_processed,
                    "cycle_number": regional["cycle"].cycle_number + 1,
                    "active_portals": len(regional.get("portal_events", [])),
                    "active_rebellion": regional.get("rebellion_event") is not None,
                    "recent_events": recent_events,
                }
            if metadata.pending_offline_report:
                try:
                    summary = json.loads(metadata.pending_offline_report)
                except (TypeError, ValueError):
                    summary = {"warning": "O relatório offline salvo não pôde ser lido; nenhuma recompensa foi creditada novamente."}
            elif decision.credited_seconds and resources is not None:
                rate = get_passive_gold_rate(db, guild)
                gold = floor(rate["total"] * decision.credited_seconds / 3600)
                materials = calculate_offline_material_rewards(
                    rate["total"],
                    decision.credited_seconds,
                    OFFLINE_CAP_SECONDS,
                )
                resources.gold += gold
                resources.crystal_reserve += materials["crystals"]
                resources.crystals += materials["crystals"]
                metadata.stamina_seconds = max(0, metadata.stamina_seconds - decision.stamina_seconds)
                summary = {
                    "report_id": str(uuid4()),
                    "elapsed_seconds": decision.elapsed_seconds,
                    "credited_seconds": decision.credited_seconds,
                    "elapsed_label": _format_elapsed(decision.elapsed_seconds),
                    "credited_label": _format_elapsed(decision.credited_seconds),
                    "gold": gold,
                    "gold_sources": gold_reward_sources(rate, decision.credited_seconds),
                    "materials": materials,
                    "crystals": materials["crystals"],
                    "gathering": gathering,
                    "stamina_spent_seconds": decision.stamina_seconds,
                    "stamina_remaining_seconds": metadata.stamina_seconds,
                    "cap_reached": decision.credited_seconds >= OFFLINE_CAP_SECONDS,
                    "cap_hours": OFFLINE_CAP_SECONDS // 3600,
                    "rate": rate,
                    "regional_context": regional_context,
                    "warning": decision.warning,
                }
                metadata.pending_offline_report = json.dumps(summary, separators=(",", ":"))
                db.add(OfflineReturnReport(
                    report_id=summary["report_id"], campaign_id=campaign_id,
                    report_json=metadata.pending_offline_report, created_at_utc=now,
                ))
            elif decision.warning or decision.elapsed_seconds >= OFFLINE_MINIMUM_SECONDS:
                summary = {
                    "report_id": str(uuid4()),
                    "elapsed_seconds": decision.elapsed_seconds,
                    "credited_seconds": 0,
                    "elapsed_label": _format_elapsed(decision.elapsed_seconds),
                    "credited_label": "0min",
                    "gold": 0,
                    "crystals": 0,
                    "gathering": gathering,
                    "regional_context": regional_context,
                    "stamina_spent_seconds": 0,
                    "stamina_remaining_seconds": metadata.stamina_seconds,
                    "warning": decision.warning or "Não havia estamina disponível para processar o período offline.",
                }
                metadata.pending_offline_report = json.dumps(summary, separators=(",", ":"))
                db.add(OfflineReturnReport(
                    report_id=summary["report_id"], campaign_id=campaign_id,
                    report_json=metadata.pending_offline_report, created_at_utc=now,
                ))
            metadata.last_session_state = "active"
            metadata.updated_at_utc = now
            db.commit()

        try:
            anchor = self.anchor_store.load(campaign_id)
            previous_high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"])) if anchor else now
        except (ClockAnchorError, KeyError, ValueError, TypeError):
            previous_high_water = now
        self.anchor_store.save(campaign_id, max(previous_high_water, now))
        self._session_started[campaign_id] = self.monotonic_clock()
        return summary

    def acknowledge_offline_report(self, campaign_id: str, report_id: str) -> bool:
        with SessionLocal() as db:
            metadata = db.get(CampaignMetadata, campaign_id)
            if metadata is None:
                return False
            if not metadata.pending_offline_report:
                history = db.get(OfflineReturnReport, report_id)
                return bool(history and history.campaign_id == campaign_id and history.acknowledged_at_utc)
            try:
                report = json.loads(metadata.pending_offline_report)
            except (TypeError, ValueError):
                return False
            if report.get("report_id") != report_id:
                return False
            history = db.get(OfflineReturnReport, report_id)
            if history is not None and history.acknowledged_at_utc is None:
                history.acknowledged_at_utc = _as_utc(self.wall_clock())
                db.add(history)
            metadata.pending_offline_report = None
            metadata.updated_at_utc = _as_utc(self.wall_clock())
            db.commit()
            return True

    def end_offline_period_in_save_picker(self, campaign_service, campaign_id: str) -> None:
        """Stop eligibility when the user keeps the app open in the save picker."""
        info = campaign_service.inspect_campaign(campaign_id)
        now = _as_utc(self.wall_clock())
        with sqlite3.connect(info.database_path) as connection:
            connection.execute(
                "UPDATE campaign_metadata SET last_session_state = 'suspended', "
                "last_clean_shutdown_utc = NULL, updated_at_utc = ? WHERE campaign_id = ?",
                (now.isoformat(), campaign_id),
            )
            connection.commit()
        try:
            anchor = self.anchor_store.load(campaign_id)
            previous_high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"])) if anchor else now
        except (ClockAnchorError, KeyError, ValueError, TypeError):
            previous_high_water = now
        self.anchor_store.save(campaign_id, max(previous_high_water, now))

    def initialize_campaign(self, campaign_id: str) -> None:
        now = _as_utc(self.wall_clock())
        try:
            anchor = self.anchor_store.load(campaign_id)
            high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"])) if anchor else now
        except (ClockAnchorError, KeyError, ValueError, TypeError):
            high_water = now
        self.anchor_store.save(campaign_id, max(high_water, now))

    def close_campaign(self, campaign_id: str, campaign_service) -> float:
        now = _as_utc(self.wall_clock())
        active_seconds = self.checkpoint_active_session(campaign_id)
        self._session_started.pop(campaign_id, None)
        try:
            anchor = self.anchor_store.load(campaign_id)
            previous_high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"])) if anchor else now
        except (ClockAnchorError, KeyError, ValueError, TypeError):
            previous_high_water = now
        self.anchor_store.save(campaign_id, max(previous_high_water, now))
        campaign_service.close_active_campaign(campaign_id, closed_at_utc=now)
        return active_seconds

    def mark_process_shutdown(self, campaign_id: str, campaign_service) -> None:
        now = _as_utc(self.wall_clock())
        self._session_started.pop(campaign_id, None)
        try:
            anchor = self.anchor_store.load(campaign_id)
            previous_high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"])) if anchor else now
        except (ClockAnchorError, KeyError, ValueError, TypeError):
            previous_high_water = now
        self.anchor_store.save(campaign_id, max(previous_high_water, now))
        # Campaigns in the picker were explicitly placed in offline mode. Preserve that
        # intent across a process exit; merely closing the picker grants no offline time.

    def suspend_campaign(self, campaign_id: str) -> datetime:
        now = _as_utc(self.wall_clock())
        self.checkpoint_active_session(campaign_id)
        self._session_started.pop(campaign_id, None)
        try:
            anchor = self.anchor_store.load(campaign_id)
            previous_high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"])) if anchor else now
        except (ClockAnchorError, KeyError, ValueError, TypeError):
            previous_high_water = now
        self.anchor_store.save(campaign_id, max(previous_high_water, now))
        with SessionLocal() as db:
            metadata = db.get(CampaignMetadata, campaign_id)
            guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign_id))
            if guild is not None:
                advance_all_assignments(db, guild, now=now)
            if metadata is not None:
                metadata.last_clean_shutdown_utc = now
                metadata.last_session_state = "offline"
                metadata.updated_at_utc = now
                db.commit()
        return now

    def checkpoint_active_session(self, campaign_id: str) -> int:
        now_monotonic = self.monotonic_clock()
        started = self._session_started.get(campaign_id)
        if started is None:
            return 0
        active_seconds = max(0, floor(now_monotonic - started))
        self._session_started[campaign_id] = now_monotonic
        with SessionLocal() as db:
            metadata = db.get(CampaignMetadata, campaign_id)
            if metadata is not None and active_seconds:
                accumulated = max(0, metadata.stamina_recharge_remainder_seconds) + active_seconds
                completed_hours, remainder = divmod(accumulated, 3600)
                metadata.stamina_seconds = min(8 * 60 * 60, metadata.stamina_seconds + completed_hours * 2 * 60 * 60)
                metadata.stamina_recharge_remainder_seconds = 0 if metadata.stamina_seconds >= 8 * 60 * 60 else remainder
                metadata.updated_at_utc = _as_utc(self.wall_clock())
            guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign_id))
            if guild is not None:
                advance_all_assignments(db, guild, now=_as_utc(self.wall_clock()))
            db.commit()
        return active_seconds

    def preview_active_stamina(
        self,
        campaign_id: str,
        stamina_seconds: int,
        recharge_remainder_seconds: int,
    ) -> dict[str, int]:
        started = self._session_started.get(campaign_id)
        active_seconds = max(0, floor(self.monotonic_clock() - started)) if started is not None else 0
        projected_stamina, projected_remainder = project_stamina_after_active_seconds(
            stamina_seconds, recharge_remainder_seconds, active_seconds,
        )
        seconds_until_recharge = (
            max(0, 3600 - projected_remainder) if projected_stamina < OFFLINE_CAP_SECONDS else 0
        )
        return {
            "stamina_seconds": projected_stamina,
            "recharge_remainder_seconds": projected_remainder,
            "active_seconds_since_checkpoint": active_seconds,
            "seconds_until_recharge": seconds_until_recharge,
            "cap_seconds": OFFLINE_CAP_SECONDS,
        }


def _format_elapsed(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}min" if hours else f"{minutes}min"


def project_stamina_after_active_seconds(
    stamina_seconds: int,
    recharge_remainder_seconds: int,
    active_seconds: int,
) -> tuple[int, int]:
    """Preview earned stamina without changing persisted campaign state."""
    stamina = min(OFFLINE_CAP_SECONDS, max(0, int(stamina_seconds)))
    if stamina >= OFFLINE_CAP_SECONDS:
        return OFFLINE_CAP_SECONDS, 0
    accumulated = max(0, int(recharge_remainder_seconds)) + max(0, int(active_seconds))
    completed_hours, remainder = divmod(accumulated, 3600)
    stamina = min(OFFLINE_CAP_SECONDS, stamina + completed_hours * 2 * 3600)
    return stamina, 0 if stamina >= OFFLINE_CAP_SECONDS else remainder
