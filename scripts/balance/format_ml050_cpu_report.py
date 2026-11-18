"""Apply review clarifications to the completed ML-050 paired CPU report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREFIX = ROOT / "reports" / "ml050_cpu_paired_2026-11-17"
PROFILE_NAMES = ("strong", "medium", "new")
VARIANTS = ("previous", "ml050")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as stream:
        temporary_path = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _fmt_pair(before: float | int, after: float | int) -> str:
    return f"{before} → {after} ({after - before:+g})"


def _fmt_percentage_points(before: float, after: float) -> str:
    before_pct = round(100 * before, 2)
    after_pct = round(100 * after, 2)
    delta_pp = round(after_pct - before_pct, 2)
    return f"{before_pct:.2f}% → {after_pct:.2f}% ({delta_pp:+.2f} p.p.)"


def _validate(report: dict[str, object], checkpoint: dict[str, object]) -> None:
    if checkpoint.get("status") != "complete":
        raise ValueError("the paired CPU checkpoint is not complete")
    source = report.get("data_source")
    if not isinstance(source, dict):
        raise ValueError("report has no data_source metadata")
    configuration_sha256 = checkpoint.get("configuration_sha256")
    if source.get("configuration_sha256") != configuration_sha256:
        raise ValueError("report and checkpoint configuration hashes differ")
    configuration = checkpoint.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("checkpoint has no configuration")
    source_hashes = configuration.get("source_sha256")
    if source.get("source_sha256") != source_hashes:
        raise ValueError("report and checkpoint source hashes differ")
    seeds = report.get("seeds")
    results = checkpoint.get("results")
    if not isinstance(seeds, list) or not isinstance(results, dict):
        raise ValueError("report seeds or checkpoint results are missing")
    if len(seeds) != 5 or report.get("horizon_cycles") != 100:
        raise ValueError("expected the original five paired 100-cycle seeds")
    if {str(seed) for seed in seeds} != set(results):
        raise ValueError("report seeds do not match checkpoint seed results")
    for seed in seeds:
        arms = results[str(seed)]
        if not isinstance(arms, dict) or set(arms) != set(VARIANTS):
            raise ValueError(f"seed {seed} does not have both paired variants")
        for variant in VARIANTS:
            profiles = arms[variant].get("profiles")
            if not isinstance(profiles, dict) or set(profiles) != set(PROFILE_NAMES):
                raise ValueError(f"seed {seed}, {variant} is missing a profile")


def _build_markdown(report: dict[str, object]) -> str:
    summaries = report["profile_summary"]
    assert isinstance(summaries, dict)
    lines = [
        "# ML-050 — comparação pareada de atividade CPU",
        "",
        f"Seeds: {', '.join(str(seed) for seed in report['seeds'])} · "
        f"{report['horizon_cycles']} Vigílias por campanha.",
        "",
        "A linha anterior usa o filtro de candidatos anterior ao ML-050. A nova linha usa a faixa de contratos "
        "por nível da guilda. Cada par reutiliza o mesmo banco de conteúdo, UUID de campanha e seed; cada braço "
        "escreve em uma pasta descartável separada.",
        "",
        "O harness avança somente as guildas CPU. A guilda do jogador permanece no nível 1; como as faixas são "
        "selecionadas pelo nível da guilda do jogador ao materializar o quadro, esta comparação de 5 × 100 ciclos "
        "mede a faixa 1–10 e não mede diretamente os cortes de nível alto.",
        "",
        "Ações contam inícios de contratos, masmorras, chefes e entradas CPU em portais. A quota de masmorras/chefes "
        "usa apenas contratos, masmorras e chefes no denominador. XP é a soma de XP de sucesso registrada em "
        "`RegionalCpuCyclePlan.xp_earned`; não inclui XP de falha e não representa o XP líquido total aplicado. "
        "Os níveis finais e ganhos abaixo são das guildas CPU; o nível médio do elenco é dos mercenários CPU ativos.",
        "",
        "Os cortes 14/15, 24/25, 29/30 e 49/50 e os níveis de mercenário CPU 1/2/3/5 têm cobertura adicional "
        "em testes curtos de fronteira. O traço adversarial de três ciclos cobre contrato elegível, fallback para "
        "masmorra/chefe e inatividade. Ele força em memória a elegibilidade do fallback e não altera as regras do jogo.",
        "",
        f"Métricas brutas por seed/variante: `{report['data_source']['checkpoint']}`. "
        f"Configuração SHA-256: `{report['data_source']['configuration_sha256']}`.",
        "",
        "| Perfil | Estados CPU | Ações totais antes → depois | Contratos | Masmorras | Chefes | Quota masmorras/chefes | XP de sucesso nos planos | Nível final da guilda CPU (ganho) | Nível médio do elenco CPU | Maior sequência sem atividade |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for profile in PROFILE_NAMES:
        row = summaries[profile]
        before = row["previous"]
        after = row["ml050"]
        before_starts = before["action_starts_by_type"]
        after_starts = after["action_starts_by_type"]
        lines.append(
            f"| {profile} | {_fmt_pair(before['cpu_guild_states'], after['cpu_guild_states'])} | "
            f"{_fmt_pair(before['activity_starts_total'], after['activity_starts_total'])} | "
            f"{_fmt_pair(before_starts['contract'], after_starts['contract'])} | "
            f"{_fmt_pair(before_starts['dungeon'], after_starts['dungeon'])} | "
            f"{_fmt_pair(before_starts['boss'], after_starts['boss'])} | "
            f"{_fmt_percentage_points(before['dungeon_boss_share_of_contract_dungeon_boss_starts'], after['dungeon_boss_share_of_contract_dungeon_boss_starts'])} | "
            f"{_fmt_pair(before['xp_earned'], after['xp_earned'])} | "
            f"{_fmt_pair(before['mean_final_guild_level'], after['mean_final_guild_level'])} "
            f"(ganho {_fmt_pair(before['mean_guild_level_gain'], after['mean_guild_level_gain'])}) | "
            f"{_fmt_pair(before['mean_final_active_mercenary_level'], after['mean_final_active_mercenary_level'])} | "
            f"{before['longest_inactive_streak']} → {after['longest_inactive_streak']} ciclos |"
        )
    lines.extend([
        "",
        "O relatório mantém o efeito observado por perfil para revisão; nenhuma compensação de CPU foi aplicada. "
        "O formato foi esclarecido depois da coleta; os dados brutos e os hashes do checkpoint não foram alterados.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    args = parser.parse_args()
    prefix = args.prefix if args.prefix.is_absolute() else ROOT / args.prefix
    report_path = prefix.with_suffix(".json")
    markdown_path = prefix.with_suffix(".md")
    checkpoint_path = prefix.with_name(f"{prefix.name}.checkpoint.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(checkpoint, dict):
        parser.error("report and checkpoint must be JSON objects")
    try:
        _validate(report, checkpoint)
    except ValueError as exc:
        parser.error(str(exc))

    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["measurement_scope"] = {
        "campaign_player_guild_level": 1,
        "contract_band_measured_by_paired_run": "1-10",
        "high_level_cutovers": "covered by separate short boundary regression, not by the 5x100 pairing",
        "xp_metric": "sum of RegionalCpuCyclePlan.xp_earned; success-plan telemetry only, excludes failure XP",
        "guild_level_metrics": "CPU guild states; final level and gain are means across CPU guild states",
        "boundary_trace": "three-cycle synthetic eligibility trace; fallback eligibility is controlled in-memory",
        "report_format_sha256": script_hash,
    }
    _atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(markdown_path, _build_markdown(report))
    print(f"JSON: {report_path}")
    print(f"Markdown: {markdown_path}")


if __name__ == "__main__":
    main()
