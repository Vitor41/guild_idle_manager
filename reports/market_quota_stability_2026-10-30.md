# Estabilidade operacional da cota do Mercado

Sensibilidade descritiva N=1 dos cinco perfis em seis cotas e reservas 30/300, mais comparação N=10 do produtor entre bases25/35/50 com reserva30, política de crafting equivalente e seeds pareadas. Todos os saves são SQLite temporários.

## Sensibilidade N=1 por perfil/cota/reserva

| Perfil | Cota L1 | Reserva | Nível Mercado | Ouro líquido | Craft: quantidade/taxa | Venda: un./ouro/% fonte bruta | Materiais finais W/M/C | Pico estoque/cap. | Overflow M/D/G/S | Coleta produzida/descartada | Pausa: h-trabalhador / checkpoints pausados/total | Nível 10/25/50 (dia) |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|
| ativo | 10 | 30 | 1 | 69084 | 0/0 | 590/4990/5.22% | 360/547/83 | 1672/1990 | 3/0/0/0 | 5727/0 | 0.0/0/0 | 13/45/74 |
| casual | 10 | 30 | 1 | 73498 | 0/0 | 428/2399/2.96% | 30/30/30 | 526/1990 | 0/0/0/0 | 360/0 | 0.0/0/0 | 26/77/131 |
| offline | 10 | 30 | 1 | 69299 | 0/0 | 650/5340/5.55% | 455/452/109 | 1662/1990 | 1/0/0/0 | 5731/0 | 0.0/0/0 | 15/49/79 |
| produtor | 10 | 30 | 1 | 82963 | 0/0 | 650/3250/3.67% | 947/528/77 | 1981/1990 | 128/8/0/0 | 2107/0 | 0.0/0/0 | 12/48/79 |
| combate | 10 | 30 | 1 | 71607 | 0/0 | 650/5240/5.32% | 420/424/58 | 1673/1990 | 3/0/0/0 | 5695/0 | 0.0/0/0 | 12/45/76 |
| ativo | 10 | 300 | 1 | 70768 | 0/0 | 550/4730/4.86% | 351/553/86 | 1671/1990 | 1/0/0/0 | 5674/0 | 0.0/0/0 | 13/45/75 |
| casual | 10 | 300 | 1 | 71183 | 0/0 | 10/50/0.06% | 220/189/101 | 946/1990 | 0/0/0/0 | 360/0 | 0.0/0/0 | 26/77/131 |
| offline | 10 | 300 | 1 | 69019 | 0/0 | 600/5060/5.28% | 501/183/109 | 1633/1990 | 0/0/0/0 | 5427/0 | 0.0/0/0 | 15/49/79 |
| produtor | 10 | 300 | 1 | 82963 | 0/0 | 650/3250/3.67% | 947/528/77 | 1981/1990 | 128/8/0/0 | 2107/0 | 0.0/0/0 | 12/48/79 |
| combate | 10 | 300 | 1 | 69985 | 0/0 | 570/4770/4.93% | 521/157/71 | 1642/1990 | 0/0/0/0 | 5439/0 | 0.0/0/0 | 12/41/74 |
| ativo | 25 | 30 | 1 | 74720 | 1/80 | 1269/9665/9.53% | 30/32/30 | 1636/1990 | 0/0/0/0 | 5498/0 | 28.37/10/24 | 13/45/75 |
| casual | 25 | 30 | 1 | 74020 | 1/80 | 420/2469/3.02% | 32/33/30 | 527/1990 | 0/0/0/0 | 360/0 | 0.0/0/3 | 26/77/130 |
| offline | 25 | 30 | 1 | 76163 | 1/80 | 1616/12231/11.86% | 100/85/94 | 1636/1990 | 0/0/0/0 | 5961/0 | 12.65/6/28 | 15/49/79 |
| produtor | 25 | 30 | 1 | 93478 | 1/80 | 1625/13125/13.23% | 820/583/94 | 1967/1990 | 28/0/0/0 | 2958/0 | 3038.7/581/772 | 12/48/79 |
| combate | 25 | 30 | 1 | 75527 | 1/80 | 1539/11863/11.59% | 115/118/58 | 1646/1990 | 0/0/0/0 | 5966/0 | 12.57/4/28 | 12/41/73 |
| ativo | 25 | 300 | 1 | 72594 | 0/0 | 993/8437/8.5% | 301/302/79 | 1646/1990 | 0/0/0/0 | 5820/0 | 0.0/0/0 | 13/45/75 |
| casual | 25 | 300 | 1 | 71203 | 0/0 | 14/70/0.09% | 216/189/101 | 942/1990 | 0/0/0/0 | 360/0 | 0.0/0/0 | 26/77/131 |
| offline | 25 | 300 | 1 | 72803 | 0/0 | 1068/8788/8.82% | 300/303/108 | 1647/1990 | 0/0/0/0 | 5834/0 | 0.0/0/0 | 15/49/79 |
| produtor | 25 | 300 | 1 | 93558 | 0/0 | 1625/13125/13.23% | 822/580/94 | 1967/1990 | 28/0/0/0 | 2955/0 | 0.0/0/0 | 12/48/79 |
| combate | 25 | 300 | 1 | 74883 | 0/0 | 1038/8512/8.36% | 300/300/58 | 1648/1990 | 0/0/0/0 | 5833/0 | 0.0/0/0 | 12/45/76 |
| ativo | 50 | 30 | 1 | 75276 | 1/80 | 1435/10715/10.51% | 30/33/30 | 1612/1990 | 0/0/0/0 | 5657/0 | 25.72/7/24 | 13/45/75 |
| casual | 50 | 30 | 1 | 74066 | 1/80 | 420/2519/3.08% | 30/35/30 | 527/1990 | 0/0/0/0 | 360/0 | 0.0/0/3 | 26/77/130 |
| offline | 50 | 30 | 1 | 77935 | 1/80 | 2067/14421/13.75% | 37/32/30 | 1612/1990 | 0/0/0/0 | 6236/0 | 8.07/5/28 | 15/49/79 |
| produtor | 50 | 30 | 1 | 130303 | 1/80 | 3250/49950/36.73% | 736/610/123 | 1942/1990 | 0/0/0/0 | 4530/0 | 3012.5/576/772 | 12/48/79 |
| combate | 50 | 30 | 1 | 74830 | 1/80 | 1615/9839/9.68% | 33/32/30 | 1603/1990 | 0/0/0/0 | 5873/0 | 14.12/6/28 | 12/41/74 |
| ativo | 50 | 300 | 1 | 70890 | 0/0 | 760/5742/5.89% | 300/302/78 | 1611/1990 | 0/0/0/0 | 5575/0 | 0.0/0/0 | 13/45/75 |
| casual | 50 | 300 | 1 | 71203 | 0/0 | 14/70/0.09% | 216/189/101 | 942/1990 | 0/0/0/0 | 360/0 | 0.0/0/0 | 26/77/131 |
| offline | 50 | 300 | 1 | 73600 | 0/0 | 1244/9596/9.55% | 300/303/113 | 1612/1990 | 0/0/0/0 | 6000/0 | 0.0/0/0 | 15/49/79 |
| produtor | 50 | 300 | 1 | 130383 | 0/0 | 3250/49950/36.73% | 738/610/120 | 1942/1990 | 0/0/0/0 | 4527/0 | 0.0/0/0 | 12/48/79 |
| combate | 50 | 300 | 1 | 74543 | 0/0 | 1286/9764/9.62% | 300/300/53 | 1623/1990 | 0/0/0/0 | 6035/0 | 0.0/0/0 | 12/45/78 |
| ativo | 100 | 30 | 1 | 85576 | 0/0 | 2399/17715/15.76% | 32/33/30 | 1351/1990 | 0/0/0/0 | 6585/0 | 0.0/0/0 | 13/45/79 |
| casual | 100 | 30 | 1 | 76030 | 0/0 | 783/4252/5.08% | 30/30/30 | 518/1990 | 0/0/0/0 | 720/0 | 0.0/0/0 | 26/77/130 |
| offline | 100 | 30 | 1 | 73539 | 0/0 | 2566/15606/15.6% | 30/32/30 | 1401/1990 | 0/0/0/0 | 6587/0 | 0.0/0/0 | 15/36/71 |
| produtor | 100 | 30 | 1 | 200033 | 0/0 | 6500/119600/58.16% | 588/660/170 | 1892/1990 | 0/0/0/0 | 7727/0 | 0.0/0/0 | 12/48/79 |
| combate | 100 | 30 | 1 | 79987 | 0/0 | 2419/14789/13.85% | 30/30/36 | 1551/1990 | 0/0/0/0 | 6630/0 | 0.0/0/0 | 12/44/75 |
| ativo | 100 | 300 | 1 | 74973 | 0/0 | 1077/7139/7.01% | 300/246/84 | 1456/1990 | 0/0/0/0 | 5814/0 | 0.0/0/0 | 13/45/79 |
| casual | 100 | 300 | 1 | 71203 | 0/0 | 14/70/0.09% | 216/189/101 | 942/1990 | 0/0/0/0 | 360/0 | 0.0/0/0 | 26/77/131 |
| offline | 100 | 300 | 1 | 68531 | 0/0 | 1658/10606/11.16% | 301/300/298 | 1553/1990 | 0/0/0/0 | 6486/0 | 0.0/0/0 | 15/36/71 |
| produtor | 100 | 300 | 1 | 200033 | 0/0 | 6500/119600/58.16% | 588/660/170 | 1892/1990 | 0/0/0/0 | 7727/0 | 0.0/0/0 | 12/48/79 |
| combate | 100 | 300 | 1 | 76395 | 0/0 | 1771/11197/10.85% | 303/300/62 | 1543/1990 | 0/0/0/0 | 6580/0 | 0.0/0/0 | 12/44/75 |
| ativo | 250 | 30 | 1 | 85437 | 0/0 | 2675/17681/15.75% | 30/35/30 | 1358/1990 | 0/0/0/0 | 6891/0 | 0.0/0/0 | 13/46/79 |
| casual | 250 | 30 | 1 | 79110 | 0/0 | 1114/5577/6.43% | 31/30/30 | 559/1990 | 0/0/0/0 | 1080/0 | 0.0/0/0 | 26/78/131 |
| offline | 250 | 30 | 1 | 84003 | 0/0 | 4109/26070/23.6% | 30/32/30 | 1198/1990 | 0/0/0/0 | 8112/0 | 0.0/0/0 | 15/36/71 |
| produtor | 250 | 30 | 1 | 356747 | 0/0 | 14925/276314/76.25% | 466/492/412 | 1844/1990 | 0/0/0/0 | 16104/0 | 0.0/0/0 | 12/48/79 |
| combate | 250 | 30 | 1 | 85964 | 0/0 | 3378/20766/18.41% | 33/32/31 | 1261/1990 | 0/0/0/0 | 7589/0 | 0.0/0/0 | 12/44/75 |
| ativo | 250 | 300 | 1 | 80071 | 0/0 | 1934/12538/11.73% | 300/303/86 | 1402/1990 | 0/0/0/0 | 6723/0 | 0.0/0/0 | 13/45/79 |
| casual | 250 | 300 | 1 | 71203 | 0/0 | 14/70/0.09% | 216/189/101 | 942/1990 | 0/0/0/0 | 360/0 | 0.0/0/0 | 26/77/131 |
| offline | 250 | 300 | 1 | 76174 | 0/0 | 2843/18249/17.78% | 301/300/298 | 1234/1990 | 0/0/0/0 | 7653/0 | 0.0/0/0 | 15/36/71 |
| produtor | 250 | 300 | 1 | 356359 | 0/0 | 14905/275926/76.23% | 466/477/411 | 1828/1990 | 0/0/0/0 | 16068/0 | 0.0/0/0 | 12/48/79 |
| combate | 250 | 300 | 1 | 85389 | 0/0 | 2894/18618/16.57% | 300/300/60 | 1247/1990 | 0/0/0/0 | 7632/0 | 0.0/0/0 | 12/45/78 |
| ativo | sem limite | 30 | 1 | 207369 | 0/0 | 20890/144383/61.73% | 31/30/30 | 852/1990 | 0/0/0/0 | 25115/0 | 0.0/0/0 | 13/43/73 |
| casual | sem limite | 30 | 1 | 79403 | 0/0 | 1508/7764/8.93% | 30/31/30 | 517/1990 | 0/0/0/0 | 1440/0 | 0.0/0/0 | 26/77/129 |
| offline | sem limite | 30 | 1 | 172127 | 0/0 | 17059/108954/54.79% | 31/36/30 | 839/1990 | 0/0/0/0 | 21246/0 | 0.0/0/0 | 15/47/76 |
| produtor | sem limite | 30 | 1 | 648218 | 0/0 | 32694/565302/86.46% | 348/441/585 | 1809/2000 | 0/0/0/0 | 33804/0 | 0.0/0/0 | 12/47/79 |
| combate | sem limite | 30 | 1 | 178544 | 0/0 | 17189/113628/55.33% | 32/30/36 | 627/1990 | 0/0/0/0 | 21378/0 | 0.0/0/0 | 12/44/75 |
| ativo | sem limite | 300 | 1 | 126401 | 0/0 | 8017/56839/37.07% | 300/239/79 | 1093/1990 | 0/0/0/0 | 12776/0 | 0.0/0/0 | 13/48/81 |
| casual | sem limite | 300 | 1 | 71203 | 0/0 | 14/70/0.09% | 216/189/101 | 942/1990 | 0/0/0/0 | 360/0 | 0.0/0/0 | 26/77/131 |
| offline | sem limite | 300 | 1 | 98284 | 0/0 | 6277/40399/32.38% | 300/201/298 | 1136/1990 | 0/0/0/0 | 11005/0 | 0.0/0/0 | 15/36/71 |
| produtor | sem limite | 300 | 1 | 386625 | 0/0 | 17603/306192/78.06% | 459/439/518 | 1890/1990 | 0/0/0/0 | 18828/0 | 0.0/0/0 | 12/48/79 |
| combate | sem limite | 300 | 1 | 102666 | 0/0 | 6308/38744/29.93% | 187/283/58 | 1012/1990 | 0/0/0/0 | 10969/0 | 0.0/0/0 | 12/44/74 |

Os casos N=1 mostram a forma dos fluxos, não diferenças populacionais. Estoque máximo histórico é o pico observado no fechamento diário após venda; o N10 instrumentado também guarda o pico antes da venda. Pausa mede segundos-trabalhador sem produção por capacidade cheia; não é descarte nem equivale a unidades fixas, pois os bônus por ciclo variam.

## Produtor N=10: cotas 25, 35 e 50

| Cota L1 | Reserva | Ouro final mediana (mín–máx) | Ouro Mercado mediana (mín–máx) | Parcela Mercado mediana (mín–máx) | Unidades vendidas mediana (mín–máx) | Overflow total M/D/G/S | Sementes com overflow M/D/G/S | Produção gathering mediana | Horas-trabalhador pausadas (total N=10) | Equivalentes de ciclo perdidos | Checkpoints pausados/total (N=10) | Pico antes/depois venda | Dias nível 10/25/50 (mediana [mín–máx]) | Nível 50 (IC95% Wilson) |
|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---|---|
| 25 | 30 | 94794 (89053–120199) | 15112 (11100–26750) | 15 (12–21)% | 1912 (1375–3950) | 135/0/0/0 | 9/0/0/0 | 3258 (2707–5076) | 41858.07 | 2511484 | 7959/10612 | 1990 (1990–2000)/1966 (1966–1978) | 12 (10–33)/58 (37–141)/86 (68–168) | 10/10 (72.2–100.0%) |
| 35 | 30 | 108964 (101333–137234) | 29190 (23380–43785) | 25 (22–30)% | 2678 (1925–5530) | 58/0/0/0 | 6/0/0/0 | 3999 (3237–6643) | 41712.52 | 2502751 | 7940/10612 | 1990 (1990–2000)/1956 (1956–1968) | 12 (10–33)/58 (37–141)/86 (68–168) | 10/10 (72.2–100.0%) |
| 50 | 30 | 130580 (119653–163049) | 51400 (41700–69600) | 37 (33–40)% | 3825 (2750–7900) | 10/0/0/0 | 2/0/0/0 | 5122 (4045–8998) | 41493.07 | 2489584 | 7931/10612 | 1990 (1990–2000)/1942 (1941–1953) | 12 (10–33)/58 (37–141)/86 (68–168) | 10/10 (72.2–100.0%) |

### Fontes, drenos e recuperação em N=10

| Cota L1 | Reserva | Ouro offline | Missões/contratos | Masmorra/portal | Mercado | Construções/contratações | Desmontagem | Crafting | Crafts | Resíduo não atribuído | Alvos bloqueados depois comprados | Bloqueios no horizonte | Entradas portal/jogador | Drops portal |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 30 | 251512 | 601743 | 29856 | 162125 | 23700 | 43650 | 480 | 6 | 0 | 30 | 0 | 0 | 0 |
| 35 | 30 | 251512 | 601743 | 29856 | 303940 | 23700 | 43650 | 480 | 6 | 0 | 30 | 0 | 0 | 0 |
| 50 | 30 | 251512 | 601743 | 29856 | 520450 | 23700 | 43650 | 480 | 6 | 0 | 30 | 0 | 0 | 0 |

### Diferença pareada: base25 menos base50

Valores abaixo são medianas e intervalo mínimo–máximo por seed pareada; números negativos indicam resultado menor em base25.

| Reserva | Ouro final | Ouro Mercado | Materiais vendidos | Overflow missão | Overflow masmorra | Overflow coleta | Overflow desmontagem | Pausa coleta (h-trabalhador) | Pico pré-venda | Dia nível 10 | Dia nível 25 | Dia nível 50 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | -36137.5 (-42850.0–-30600.0) | -36137.5 (-42850.0–-30600.0) | -1912.5 (-3950.0–-1375.0) | 13.0 (0.0–25.0) | 0.0 (0.0–0.0) | 0.0 (0.0–0.0) | 0.0 (0.0–0.0) | 31.2 (22.3–65.4) | 0.0 (0.0–0.0) | 0.0 | 0.0 | 0.0 |

Regra versionada: `25 + 5 * (market_level // 5); L1-4=25, L5-9=30, L10-14=35, L100=125`. A base35 é somente o ponto intermediário experimental, não um novo marco da fórmula.

### Leitura e limites

M/D/G/S significa unidades de materiais descartadas por claims reais de missão/contrato, masmorra/portal, coleta e desmontagem, respectivamente, por falta de capacidade. São unidades de loot perdidas (não ouro nominal ou contagem de eventos); os valores vêm dos contadores de overflow dos serviços. Perda de loot continua sendo custo econômico. Pausa é registrada em segundos-trabalhador pelo serviço; convertida para horas-trabalhador, ela mede tempo de coleta que a regra de capacidade não reconhece, não equivale a unidades fixas pois o bônus por ciclo pode variar.

A reserva 30/300 é uma política experimental do harness, não regra do jogador. Ela protege explicitamente materiais excedentes e, portanto, muda venda, ouro, estoque, gathering e capacidade. Nesta rodada usa-se a política representativa de reserva30; análises antigas com reserva300 permanecem separadas como sensibilidade do harness, não uma regra alternativa.

O limite do Mercado 1 equivale a 2,08%, 5,21%, 10,42%, 20,83% ou 52,08% da produção base de 480 unidades de um trabalhador em 8h. A fórmula aprovada acrescenta 5 unidades em níveis múltiplos de cinco: base25 chega a 125 no nível100 (26,04% dessa referência); base50 chega a 150 (31,25%).

O runner tenta participar de portal natal naturalmente ativo em janela online e registra início, claim e loot por serviços reais; uma ocorrência ausente permanece ausente, sem geração forçada. Os contadores distinguem entradas/loot do jogador dos eventos regionais apenas gerados ou expirados. Rebelião continua sem participação do jogador nesta política. A política experimental de crafting fabrica até um equipamento se receita e excedente protegido estiverem disponíveis; isso mede alcance condicional, não aprova uma regra obrigatória. Nenhuma destas amostras fecha estabilidade de longo prazo, softlock global ou gate Stage 5.

## Critério operacional proposto para acompanhamento

A cada perfil e horizonte (30/90/180 dias e nível50), publicar: fontes e drenos brutos/líquidos por tipo; participação do Mercado na renda; unidades por família e proporção da referência offline 8h; estoque final/pico pré-venda/capacidade; overflow M/D/G/S; horas-trabalhador pausadas e unidades descartadas; recuperação do mesmo bloqueio por compra; progressão de níveis 10/25/50; EV dos ciclos fechados de arbitragem. O produto ainda precisa definir faixa aceitável de ouro e inflação para um horizonte longo; sem isso, o indicador mede pressão e perdas, não uma nota binária de equilíbrio.

## Reexecução

```powershell
.venv-desktop\Scripts\python.exe scripts\balance\build_market_quota_stability_report.py
```
