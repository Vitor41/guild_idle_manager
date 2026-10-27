"""Offline reward and trusted-wall-clock policy for local campaigns."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from math import floor
from time import monotonic
from typing import Callable, Protocol

from sqlalchemy import select

from app.core.game_balance import OFFLINE_CAP_SECONDS, OFFLINE_MINIMUM_SECONDS
from app.database.connection import SessionLocal
from app.models import CampaignMetadata, Guild
from app.repositories.guild_repository import get_resources_by_guild_id
from app.repositories.item_repository import add_inventory_quantity
from app.services.building_service import get_material_quantity_bonus
from app.services.offline_progress_service import (
    _canonical_material,
    calculate_offline_material_rewards,
    get_passive_gold_rate,
)


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
            raise ClockAnchorError("A protecao DPAPI esta disponivel apenas no Windows.")
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
            raise ClockAnchorError("Nao foi possivel validar a ancora protegida pelo Windows.")
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
            raise ClockAnchorError("A ancora de tempo da campanha esta ausente ou corrompida.") from exc

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
        raise ClockAnchorError("LOCALAPPDATA nao esta definido para armazenar a ancora de tempo.")
    return DpapiAnchorStore(Path(local_app_data) / "GuildIdleManager" / "clock-guard")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ClockDecision:
    elapsed_seconds: int = 0
    credited_seconds: int = 0
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
    ) -> ClockDecision:
        now = _as_utc(now_utc or self.wall_clock())
        if session_state in {"created", "initializing", "suspended"}:
            return ClockDecision()
        if session_state != "closed" or closed_at_utc is None:
            return ClockDecision(warning="A sessao anterior nao teve encerramento limpo; progresso retroativo ignorado.")
        try:
            anchor = self.anchor_store.load(campaign_id)
        except ClockAnchorError:
            return ClockDecision(warning="A ancora de tempo esta corrompida; nenhum progresso retroativo foi concedido.")
        if anchor is None:
            return ClockDecision(warning="A ancora de tempo nao existe; nenhum progresso retroativo foi concedido.")
        try:
            high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"]))
        except (KeyError, ValueError, TypeError):
            return ClockDecision(warning="A ancora de tempo esta invalida; nenhum progresso retroativo foi concedido.")
        closed_at = _as_utc(closed_at_utc)
        if now < high_water or now < closed_at:
            return ClockDecision(warning="O relogio voltou antes do ultimo marco confiavel; progresso pausado.")
        interval_start = max(closed_at, high_water)
        elapsed = max(0, floor((now - interval_start).total_seconds()))
        if elapsed < OFFLINE_MINIMUM_SECONDS:
            return ClockDecision(elapsed_seconds=elapsed)
        return ClockDecision(
            elapsed_seconds=elapsed,
            credited_seconds=min(elapsed, OFFLINE_CAP_SECONDS),
            warning="O tempo offline foi limitado ao teto configurado." if elapsed > OFFLINE_CAP_SECONDS else None,
        )

    def activate_campaign(self, campaign_id: str) -> dict[str, object] | None:
        now = _as_utc(self.wall_clock())
        with SessionLocal() as db:
            metadata = db.get(CampaignMetadata, campaign_id)
            guild = db.scalar(select(Guild).where(Guild.campaign_id == campaign_id))
            if metadata is None or guild is None:
                raise ValueError("A campanha nao possui uma guilda valida para abrir.")
            previous_state = metadata.last_session_state
            closed_at = metadata.last_clean_shutdown_utc
            decision = self.evaluate_return(campaign_id, previous_state, closed_at, now)
            resources = get_resources_by_guild_id(db, guild.id)
            summary: dict[str, object] | None = None
            if decision.credited_seconds and resources is not None:
                rate = get_passive_gold_rate(db, guild)
                gold = floor(rate["total"] * decision.credited_seconds / 3600)
                materials = calculate_offline_material_rewards(
                    rate["total"],
                    decision.credited_seconds,
                    OFFLINE_CAP_SECONDS,
                    get_material_quantity_bonus(db, guild.id),
                )
                resources.gold += gold
                for family, quantity_key in (("wood", "wood_total"), ("ore", "ore_total"), ("gem", "crystals")):
                    quantity = materials[quantity_key]
                    if quantity > 0:
                        template = _canonical_material(db, family)
                        if template is not None:
                            add_inventory_quantity(db, guild.id, template.id, quantity)
                summary = {
                    "elapsed_seconds": decision.elapsed_seconds,
                    "credited_seconds": decision.credited_seconds,
                    "gold": gold,
                    "materials": materials,
                    "warning": decision.warning,
                }
            elif decision.warning:
                summary = {"elapsed_seconds": decision.elapsed_seconds, "credited_seconds": 0, "gold": 0, "warning": decision.warning}
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
        started = self._session_started.pop(campaign_id, self.monotonic_clock())
        active_seconds = max(0.0, self.monotonic_clock() - started)
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
        campaign_service.mark_campaign_closed(campaign_id, now)

    def suspend_campaign(self, campaign_id: str) -> None:
        now = _as_utc(self.wall_clock())
        self._session_started.pop(campaign_id, None)
        try:
            anchor = self.anchor_store.load(campaign_id)
            previous_high_water = _as_utc(datetime.fromisoformat(anchor["high_water_utc"])) if anchor else now
        except (ClockAnchorError, KeyError, ValueError, TypeError):
            previous_high_water = now
        self.anchor_store.save(campaign_id, max(previous_high_water, now))
