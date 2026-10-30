# Gates de conteúdo dos primeiros marcos — Stage 5

Conteúdo atual seedado em SQLite temporário · 2026-10-29T11:22:09.968498+00:00.

Este levantamento mede disponibilidade de catálogo pelos gates do serviço, não dias de campanha nem conclusão de atividade.

| Perfil | Grupo | Nível da primeira missão elegível com equipamento | Missões/drop únicos | Drop-base min/mediana/máx. | Primeira masmorra normal após Exploradores 1 | Sucesso base |
|---|---:|---:|---:|---:|---|---:|
| ativo | 3 | 1 | 1/1 | 25/25/25% | Ruínas das Runas Profundas (guilda/mercenário ≥4, grupo 3) | 77% |
| casual | 2 | 1 | 7/7 | 25/40/40% | Covil da Lua de Caça (guilda/mercenário ≥1, grupo 2) | 68% |
| offline | 3 | 1 | 1/1 | 25/25/25% | Ruínas das Runas Profundas (guilda/mercenário ≥4, grupo 3) | 77% |
| produtor | 2 | 1 | 7/7 | 25/40/40% | Covil da Lua de Caça (guilda/mercenário ≥1, grupo 2) | 68% |
| combate | 3 | 1 | 1/1 | 25/25/25% | Ruínas das Runas Profundas (guilda/mercenário ≥4, grupo 3) | 77% |

## Gates regionais

Portal: ameaça ≥70.0, chance inicial 5.0% até teto 25.0%; prazo de entrada 3.0h também durante catch-up offline. Rebelião: ameaça ≥85.0 e segurança ≤25.0, chance 2.0% por Vigília elegível.

Chance condicional de pelo menos um portal após 1/10/20 oportunidades elegíveis: ameaça 70: 5.0/40.13/64.15%; ameaça 85: 15.0/80.31/96.12%; ameaça 100: 25.0/94.37/99.68%. Rebelião, dado que cada Vigília é elegível: 1 Vigílias: 2.0%; 10 Vigílias: 18.29%; 50 Vigílias: 63.58%; 100 Vigílias: 86.74%. Não é prazo de campanha.

Ainda sem estimativa por perfil: dias até primeiro equipamento, masmorra e evento. As curvas regionais são condicionais a oportunidades elegíveis, chance fixa e slot livre; não modelam progresso de ameaça/segurança nem supressão por evento ativo. A rota financiada atual não compra Exploradores 1 nem simula drops por ação. A matriz registra essas lacunas para o gate; este relatório não as transforma em prova de alcance ou softlock.

## Reprodução

```powershell
.venv\Scripts\python.exe scripts\balance\audit_stage5_content_milestones.py
```
