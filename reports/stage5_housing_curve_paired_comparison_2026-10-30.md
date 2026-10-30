# Comparação pareada da curva do Alojamento — Stage 5

Data: 30/10/2026. Duas sensibilidades comparam a curva antiga à curva 1–100 aprovada: mesmas 10 seeds por perfil (50 trajetórias), fresh-save SQLite temporário, horizonte até 365 dias e a fórmula original de custo mantida. A única mudança de regra no replay válido é a capacidade por nível: vaga 1 no nível 1, vaga 20 somente no nível 100. O custo segue a exceção L1=10 ouro e a fórmula integral a partir do L2.

## Resultado pareado

| Perfil | Dias até guilda 50, mediana antiga → nova | Campo de Treino 1, mediana antiga → nova | Plano finito completo, antiga → nova | Stall modelado por 14 dias, antiga → nova | Pausa por capacidade, antiga → nova |
|---|---:|---:|---:|---:|---:|
| Ativo | 52 → 103 (+51) | 32,5 → 110,5 (+78) | 10/10 → 10/10 | 0/10 → 0/10 | 0/10 → 0/10 |
| Casual | 87,5 → 95 (+7,5) | 9 → 24 (+15) | 10/10 → 10/10 | 0/10 → 0/10 | 0/10 → 0/10 |
| Offline | 44,5 → 85,5 (+41) | 30 → 98 (+68) | 10/10 → 9/10 | 0/10 → 0/10 | 0/10 → 0/10 |
| Produtor | 45 → 57 (+12) | 5 → 24 (+19) | 10/10 → 10/10 | 0/10 → 0/10 | 10/10 → 10/10 |
| Combate | 52 → 104 (+52) | 33 → 110 (+77) | 10/10 → 10/10 | 0/10 → 0/10 | 0/10 → 0/10 |

O plano finito inclui Campo de Treino 1 como investimento-alvo opcional; não é pré-requisito para chegar à guilda 50. A trajetória offline que não o compra é seed `2026303005`: chega à guilda 50 no dia 84 e termina no dia 97 com nível de guilda 66, 64.818 ouro, mas sem madeira/minério para o custo de 10 madeira + 10 minério. A medição não registrou stall obrigatório de 14 dias. Portanto, 9/10 é uma compra opcional não concluída no horizonte do harness, não uma campanha sem rota até o nível 50.

A diferença de tempo é material e permanece aberta para decisão de produto: com custos preservados, a sensibilidade da nova curva desacelera ativo, offline e combate em cerca de 41–52 dias frente à execução pareada da curva antiga. Não existe prazo-alvo aprovado para o marco 50. A amostra identifica custo e bloqueios da política modelada; não basta para afirmar que o jogo está balanceado.

Os perfis que mantêm nove mercenários alcançam essa capacidade no nível 40, contra nível 15 na curva antiga, devido à distribuição das vagas ao longo de 1–100. A rota passa por mais compras de Alojamento e requisitos de guilda; a função de preço segue intacta.

Um piloto complementar do runner com serviços reais, campanha fresh-save e política ativo/roster_first (seed `2026103017`, N=1) chegou à guilda 50 no dia 59 e concluiu seus alvos planejados no dia 62. O nível 2 do Alojamento foi comprado no dia 5 pelo preço esperado de 200 ouro + 40 madeira. Não houve upgrade-alvo pendente ao encerrar. Portais surgiram desde o dia 47 (27 criados, 26 encerrados ou expirados), mas a equipe não cumpriu os requisitos para entrar: entradas e sucessos do jogador foram 0. Esse resultado não é pareado à curva antiga e não substitui as 10 seeds modeladas: runner, ações e caminho de economia diferem; serve como evidência de serviço e de um único percurso, não como comparação de cadência nem frequência de eventos. Ver [ledger e resumo do piloto](stage5_housing_curve_actual_service_ativo_2026-10-30.md).

## Acesso à 20ª vaga

O teste `test_funded_housing_service_reaches_level_100_and_twentieth_slot` aplica os upgrades 51–100 por `upgrade_guild_building` em fixture SQLite financiada, com guilda nível 50 e materiais disponíveis. O serviço chega ao nível 100, `get_mercenary_limit` retorna 20, preserva mercenários existentes e rejeita o próximo upgrade. Isso prova o acesso técnico ao nível 100 quando financiado, não a acessibilidade natural por perfil. Uma segunda fixture confirma que recalcular a capacidade abaixo do elenco atual não remove mercenários.

## Limites

As curvas pareadas são um modelo de sensibilidade financiada: renda, custos e cotações usam funções atuais, mas compras, contratação, escolha de atividades e coleta são simuladas pelo harness. O piloto real é somente uma semente e usa política distinta. Em conjunto, medem rota modelada e execução pontual por serviços; não estabelecem softlock econômico global, estabilidade nem participação humana. Com N=10, intervalos de taxa binária permanecem largos (0/10 stalls tem IC95% Wilson superior de 27,75%).

Os JSONs de trajetória e baseline pareado permanecem locais e não foram incluídos neste commit. Uma tentativa intermediária de desconto de custos foi descartada porque alterava o custo aprovado do nível 2; seus arquivos locais estão marcados como inválidos para a regra atual.
