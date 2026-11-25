# Portais e auditoria visual - coordenação

## Entrega autorizada em 2026-11-24

- Meta global neste chat coordenador; DEV implementa, DA dirige/audita a interface e CR revisa commits imutáveis de forma independente.
- Uma única branch: `feature/anomalies-ui-audit`, base `986b6b7c885c3a2bc8564ebc61514c3e0099223e` (`origin/main`, conteúdo publicado 0.10.0 mais histórico documental).
- Escopo: ML-052, ML-053, ML-054 e ML-055, mais no máximo dois lotes de ajustes derivados da auditoria, a registrar como melhorias após o levantamento. BUG-013 recebeu aceite do usuário e está encerrado.
- Preservar anotações locais em `ML-BUGS.md` e alteração preexistente em `scripts/balance/simulate_regional_cpu_campaigns.py`; não incluir arquivos alheios por staging indiscriminado.

## Segurança da auditoria

O usuário autorizou abrir o jogo e navegar por toda a plataforma no save real para inspeção visual. Não iniciar atividades, coletar, gastar, comprar, recrutar, equipar, resetar, importar/restaurar ou manipular o relógio. A navegação pode disparar a atualização temporal normal do próprio jogo; não usar isso para forçar eventos ou progresso. Não editar o banco original. Para estados que exijam ações, usar campanha sintética ou cópia descartável, claramente distinguida da observação do save real. Capturas privadas ficam locais e minimizadas; não publicar saves, logs privados ou dados da campanha.

## Ordem e gates

1. DEV: checkpoint de baseline; implementar ML-054 com parâmetros centralizados, versão de regras, persistência e testes de sorteios elegíveis, stacks, cooldown em horas, rollback e ausência. Entregar SHA e relatório de simulação sem mudar interface antes da direção DA.
2. DA: auditar todos os menus e fluxos navegáveis do jogo instalado, com matriz de cobertura e evidência local; definir UX de ML-052/055. Consolidar achados em um ou dois lotes coesos, sem limitar a auditoria aos exemplos prévios.
3. Coordenação: fechar o escopo dos lotes derivados e responder dúvidas de produto; encaminhar ao DEV instruções verificáveis. Não atribuir ao DEV decisões de regra ainda em aberto.
4. DEV: entregar central de eventos, comunicação visual, participação CPU e lotes derivados, mantendo snapshots, requisitos e dados. Atualizar Guia e Markdown pela mesma fonte.
5. CR: revisar cada SHA concluído; achados voltam ao DEV na mesma branch. DA revalida estados visuais, responsividade, foco e navegação. Não confundir evidência sintética com observação real.
6. Integração: testar interações, migrações, segurança, exportação, navegação parcial e ausência; verificar cobertura de todas as telas auditadas e todos os critérios do artefato.
7. Só após entrega integral e aprovações sem achados: push, PR, merge, tag e workflow de release com manifesto assinado. Confirmar artefatos e assinatura e atualizar o histórico após publicar. Aceite manual do usuário é posterior; ML-028 segue pendente desse aceite, não de implementação automática.

## Estado inicial

### Decisão de conteúdo e participação CPU

Pré-flight CR no baseline confirmou que, em quatro templates do pool nos estágios 50/100, três são inviáveis para todas as CPUs recém-semeadas; exigem equipamento que o modelo atual não obtém. Essa amostra não mede CPUs evoluídas. Na ML-055, não criar um sistema novo de equipamento NPC nem relaxar requisitos: escolher conteúdo ativo com loot que pelo menos um ator real nativo tenha capacidade de cumprir. Na região natal, manter o teto de progressão do jogador e considerar a união de capacidades jogador/CPU; não excluir desafio viável para o jogador só por ser inviável para a CPU. Em regiões externas, usar a progressão das próprias guildas CPU, não a guilda do jogador como teto global. A ocupação momentânea não define capacidade potencial de conteúdo; disponibilidade real define o agendamento.

Nas novas regras, remover o pré-sorteio de 25% de entrada CPU e priorizar a avaliação de portal viável, mantendo uma entrada por guilda/evento e combate real. Persistir motivos objetivos de não participação. Portais podem terminar depois do fechamento da Vigília/janela se iniciados no prazo, sem antecipar resultados/XP e com equipe ocupada até a conclusão real. Equivalência visita/ausência/retry é requisito. A ausência de encontro viável bloqueia geração com diagnóstico, sem consumir falha do stack. Implementação desta decisão pertence a ML-055, em SHA separado da fórmula de ML-054.

| Frente | Estado | Próximo gate |
| --- | --- | --- |
| ML-054 | Núcleo aprovado pelo CR: `4999670`; evidência `faefcd2` | 45 testes independentes, migração/legado/retry e oito casos da simulação reproduzidos. Integração ML-055 pendente; sem publicação. +5 p.p. nas cinco regiões é sensibilidade, não campanha real; janela perdida depende de presença ilustrativa |
| ML-053 | Levantamento real realizado; validação da implementação pendente | 36 achados/oportunidades e 62 evidências privadas locais; cobertura e lacunas em `reports/ml053_coverage_checkpoint_2026-11-24.md` |
| ML-052 | Aprovada por CR e DA: núcleo `897fde9`, ajuste `64d6d34f7f2482938fb304a5d6e60e5c93016210` | Relatório `reports/ml052_da_64d6d34_2026-11-24.md`; cinco larguras e reflow equivalente a 200%, não zoom nativo WebView2. Sem aceite manual ou publicação |
| ML-055 | Backend aprovado pelo CR em `043cb5eceac1bc160c76350cf3a4b628bac2f200`; central aprovada por CR e DA em `5fe567968fb53803e3873b7bb5c68f94266b1fa6` | CR repetiu 73 Python + 12 JS + 1 smoke. DA fechou estados, foco, seleção, expiração externa com contagens 0/0 e retry em `reports/ml055_da_5fe5679_2026-11-25.md`. Integração ML-056/057 e gate de publicação continuam pendentes; sem build/instalação/publicação |
| ML-056 | Escopo aprovado pela coordenação | Estados, requisitos e decisões visuais; IDs Fxx e aceite detalhados no artefato |
| ML-057 | Escopo aprovado; F34 aprovado por CR e DA em `2bb187850bf66021c19e0a128c4103560db7a3fa` | Busca parcial/loader seguro e submits Enter/botão para encontrado/ausente/vazio; evidência `reports/ml057_f34_2bb1878_2026-11-25.md`. Continuar F01–F07, F14, F16 modal, F17, F19, F30–31, F32 navegação e F35–36; ML-056 integral continua obrigatório |
| Publicação | Não iniciada | Todos os itens entregues e CR/DA aprovados |
