# ML-017 — Auditoria de preços de equipamentos

Foram auditados 1700 equipamentos gerados pelo catálogo e 20 comparações tipo/raridade/Mercado. Resultado estritamente crescente em todos os casos: **True**.

## Ouro-base Comum por tipo de equipamento

| Tipo / espaço | Ouro-base Comum |
|---|---:|
| main_hand | 24 |
| shield | 23 |
| chest | 30 |
| helmet | 22 |
| gloves | 18 |
| boots | 18 |
| ring | 16 |
| necklace | 17 |
| earring | 15 |
| belt | 16 |

## Acréscimo por raridade

| Raridade | Acréscimo sobre o Comum |
|---|---:|
| common | +0% |
| uncommon | +15% |
| rare | +35% |
| epic | +60% |
| legendary | +90% |
| mythic | +125% |

## Bônus do Mercado testados

Mercado nível 1: +0%; Mercado nível 100: +30%. Os bônus foram aplicados aos preços unitários com o serviço real `market_sale_unit_value`.

O preço Comum fica fixo por espaço de equipamento. Para cada tipo, o cálculo aplica o acréscimo de raridade com arredondamento para cima; todos os níveis de Mercado preservam diferença estrita entre raridades comparáveis com mesmo tipo, nível do item e refino. Nível do item e refino não entram no preço unitário de venda; tier não desloca a referência Comum.

Faixa econômica auditada: no Mercado nível 1, Common vai de 15 ouro e o maior preço Mythic é 68 (diferença máxima Common→Mythic do mesmo tipo: 38); no nível 100, os valores são 19, 88 e 49 ouro, respectivamente.

Os testes também verificam que a atualização do catálogo altera valores gerados pela fórmula antiga e preserva um preço administrativo customizado.
