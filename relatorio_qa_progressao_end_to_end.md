# Relatório QA de Progressão End-to-End

## Sumário executivo

A simulação compara rotas de missão, coleta, missões longas, masmorras, chefes e loot após o pacote PRD 2.
O farm ativo permanece a principal fonte de XP e ouro; coleta mantém domínio de materiais; idle e missões longas são complementares.

## Progressão por faixa

| Faixa | Missões | Coletas | Longas | XP/h missão | XP/h coleta | Ouro/h missão | Ouro/h coleta | Materiais/h |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1-20 | 140 | 40 | 3 | 1367.0 | 1125.6 | 373.8 | 298.5 | 37.37 |
| 21-50 | 170 | 70 | 3 | 3749.8 | 2537.8 | 1051.1 | 570.8 | 12.85 |
| 51-100 | 220 | 80 | 3 | 5638.2 | 3841.0 | 1340.9 | 737.7 | 9.22 |
| 101-130 | 150 | 60 | 3 | 6201.9 | 4247.8 | 1357.4 | 756.0 | 5.99 |
| 131-200 | 280 | 90 | 2 | 7631.9 | 5267.7 | 1467.6 | 832.2 | 5.41 |
| 201-250 | 230 | 70 | 2 | 8143.7 | 5662.4 | 1430.9 | 826.8 | 3.86 |
| 251-300 | 230 | 70 | 2 | 8638.1 | 6039.4 | 1412.4 | 828.7 | 3.29 |
| 301-350 | 240 | 70 | 2 | 8977.0 | 6314.6 | 1366.3 | 815.8 | 2.86 |

## Volume estimado por faixa

| Faixa | XP necessário | Missões ativas estimadas | Ouro esperado durante progressão |
|---|---:|---:|---:|
| 1-20 | 19000 | 86 | 5096 |
| 21-50 | 101500 | 95 | 28736 |
| 51-100 | 367500 | 122 | 87523 |
| 101-130 | 333500 | 78 | 73410 |
| 131-200 | 1138500 | 145 | 219073 |
| 201-250 | 1102500 | 107 | 195459 |
| 251-300 | 1347500 | 103 | 221692 |
| 301-350 | 1592500 | 101 | 244402 |

## Tempo estimado por perfil

Valores em dias corridos considerando o padrão diário descrito no PRD.

| Perfil | Nível 20 | Nível 50 | Nível 100 | Nível 200 | Nível 350 |
|---|---:|---:|---:|---:|---:|
| Ativo | 2.78 | 8.49 | 21.79 | 63.15 | 158.74 |
| Híbrido | 3.52 | 10.88 | 27.64 | 77.53 | 186.27 |
| Casual/idle | 4.34 | 13.32 | 32.86 | 87.39 | 197.27 |

## Nível 1 ao 10

| Rota | Execuções estimadas | Horas ativas | Ouro esperado |
|---|---:|---:|---:|
| Missões normais | 54 | 4.23 | 932 |
| Coletas | 78 | 4.9 | 861 |

## Distribuição de equipamentos

Simulação determinística de 1000 execuções por tipo de conteúdo.

| Conteúdo | Comum | Incomum | Raro | Épico | Lendário | Mítico |
|---|---:|---:|---:|---:|---:|---:|
| Missão | 135 | 79 | 32 | 5 | 0 | 1 |
| Coleta | 156 | 16 | 1 | 0 | 0 | 0 |
| Masmorra | 78 | 61 | 65 | 29 | 11 | 0 |
| Chefe | 65 | 33 | 57 | 43 | 31 | 2 |

## Rotas mais eficientes

- **1-20**: XP em `Dominar a Batalha de Sinais Misteriosos em Estrada do Carvalho`; ouro em `Revelar Feras Desgarradas em Bosque dos Sinos`; materiais em `Coletar Madeira de Carvalho em Arredores da Guilda`.
- **21-50**: XP em `Revelar Relíquia Desaparecida em Mata das Corujas`; ouro em `Revelar Relíquia Desaparecida em Mata das Corujas`; materiais em `Recuperar Fragmentos Sagrados em Fronteira Cinzenta`.
- **51-100**: XP em `Decifrar Acampamento Inimigo em Pântano Luminoso`; ouro em `Decifrar Acampamento Inimigo em Pântano Luminoso`; materiais em `Coletar Madeira de Carvalho em Serra de Ferro`.
- **101-130**: XP em `Decifrar Sentinelas Corrompidas em Cordilheira Rúnica`; ouro em `Decifrar Sentinelas Corrompidas em Cordilheira Rúnica`; materiais em `Coletar Madeira de Carvalho em Terras Arcanas`.
- **131-200**: XP em `Revelar Mensageiros da Guilda em Ermos Imperiais`; ouro em `Revelar Mensageiros da Guilda em Ermos Imperiais`; materiais em `Coletar Madeira de Carvalho em Marchas Sombrias`.
- **201-250**: XP em `Revelar Mercadores Isolados em Fenda Celeste`; ouro em `Revelar Mercadores Isolados em Fenda Celeste`; materiais em `Coletar Madeira de Carvalho em Domínios Dracônicos`.
- **251-300**: XP em `Revelar Mercadores Isolados em Céu Estilhaçado`; ouro em `Revelar Mercadores Isolados em Céu Estilhaçado`; materiais em `Coletar Madeira de Carvalho em Abismo Primordial`.
- **301-350**: XP em `Revelar Mercadores Isolados em Aurora Extinta`; ouro em `Revelar Mercadores Isolados em Aurora Extinta`; materiais em `Coletar Madeira de Carvalho em Limiar do Fim`.

## Achados e gargalos

- **Observação**: Missões normais entregam 1.21x XP/h e 1.25x ouro/h contra coleta no early game.
- **Observação**: Todas as faixas possuem Missões Longas válidas; opções podem ser desativadas intencionalmente pelo admin.
- **Baixo**: 20 coletas duplicadas foram desativadas mantendo os gaps por material.

## Auditoria das coletas

Foram desativadas 20 duplicidades. 40 coletas early tiveram XP/ouro graduados e 140 missões normais foram revisadas contra o piso competitivo.

- Removida `Separar Troncos Resistentes em Arredores da Guilda` (nível 1, wood); mantida a missão #1668.
- Removida `Prospectar Veios Metálicos em Arredores da Guilda` (nível 2, ore); mantida a missão #1669.
- Removida `Catalogar Flores Raras em Arredores da Guilda` (nível 3, herb); mantida a missão #1670.
- Removida `Preparar Peles Resistentes em Arredores da Guilda` (nível 4, leather); mantida a missão #1671.
- Removida `Preparar Fios Silvestres em Arredores da Guilda` (nível 5, cloth); mantida a missão #1672.
- Removida `Localizar Gemas Rúnicas em Arredores da Guilda` (nível 6, gem); mantida a missão #1673.
- Removida `Catalogar Fragmentos Sagrados em Arredores da Guilda` (nível 7, relic); mantida a missão #1674.
- Removida `Recolher Resíduos Mágicos em Arredores da Guilda` (nível 8, essence); mantida a missão #1675.
- Removida `Coletar Resina Antiga em Arredores da Guilda` (nível 9, wood); mantida a missão #1676.
- Removida `Extrair Pedra Mineral em Arredores da Guilda` (nível 10, ore); mantida a missão #1677.
- Removida `Colher Raízes Alquímicas em Arredores da Guilda` (nível 11, herb); mantida a missão #1678.
- Removida `Rastrear Partes de Criatura em Arredores da Guilda` (nível 12, leather); mantida a missão #1679.
- Removida `Separar Tecidos Naturais em Arredores da Guilda` (nível 13, cloth); mantida a missão #1680.
- Removida `Garimpar Fragmentos Luminosos em Arredores da Guilda` (nível 14, gem); mantida a missão #1681.
- Removida `Recuperar Insígnias Perdidas em Arredores da Guilda` (nível 15, relic); mantida a missão #1682.
- Removida `Extrair Ecos Elementais em Arredores da Guilda` (nível 16, essence); mantida a missão #1683.
- Removida `Cortar Resina Antiga em Arredores da Guilda` (nível 17, wood); mantida a missão #1684.
- Removida `Minerar Pedra Mineral em Arredores da Guilda` (nível 18, ore); mantida a missão #1685.
- Removida `Buscar Raízes Alquímicas em Arredores da Guilda` (nível 19, herb); mantida a missão #1686.
- Removida `Recolher Partes de Criatura em Arredores da Guilda` (nível 20, leather); mantida a missão #1687.

## Custos acumulados das construções

Valores calculados a partir dos custos globais e da curva atual; ajudam a localizar gargalos de ouro, madeira e minério.

| Construção | Ouro nv.10 | Madeira nv.10 | Minério nv.10 | Ouro nv.50 | Madeira nv.50 | Minério nv.50 |
|---|---:|---:|---:|---:|---:|---:|
| Alojamento | 5500 | 1100 | 0 | 190250 | 38050 | 0 |
| Campo de Treino | 6600 | 550 | 550 | 228300 | 19025 | 19025 |
| Ferreiro | 8250 | 0 | 1375 | 285375 | 0 | 47562 |
| Armazem | 4950 | 1650 | 0 | 171225 | 57075 | 0 |
| Escritório de Missões | 9900 | 1100 | 1100 | 342450 | 38050 | 38050 |
| Exploradores | 8800 | 1100 | 550 | 304400 | 38050 | 19025 |
| Taverna | 7700 | 1375 | 275 | 266350 | 47562 | 9512 |
| Mercado | 7150 | 1100 | 275 | 247325 | 38050 | 9512 |
| Docas | 27500 | 5500 | 2750 | 951250 | 190250 | 95125 |

## Economia e recomendações

- Missões normais devem permanecer a escolha de XP, ouro e equipamento comum.
- Coletas devem permanecer a fonte previsível de materiais; o bônus do Armazém reduz repetição sem substituir atividade.
- Idle offline entrega madeira e minério básicos em ritmo controlado e somente 1 cristal no teto efetivo.
- Missões longas não entregam itens e operam a 50% do melhor farm ativo bruto por hora.
- Masmorras e Chefes mantêm chances superiores para raridades altas, mas a massa atual merece curadoria futura por uso real.

## Evidências

Os cálculos usam templates ativos, duração, chance base, recompensa e drops persistidos no PostgreSQL. Falhas de missões comuns concedem 25% do XP; missões longas falhas não concedem XP.