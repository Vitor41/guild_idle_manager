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

| Frente | Estado | Próximo gate |
| --- | --- | --- |
| ML-054 | Baseline 32/32; desenho aprovado | Configuração central versionada, marcador nullable por ciclo e estado único campanha/região; primeiro SHA testado pendente |
| ML-053 | Auditoria real em andamento | Instalação localizada após autorização de leitura; campanha aberta pela DA. Inventário completo e lotes ainda pendentes |
| ML-052/055 | Direção visual aprovada pela coordenação | `docs/art_direction/ML052_ML055_VISUAL_SPEC.md`; componentes compactos, rota `/regional/events` e estados verificáveis. Não equivale a auditoria concluída |
| Lotes derivados | A definir após auditoria | No máximo dois, implementados nesta branch |
| Publicação | Não iniciada | Todos os itens entregues e CR/DA aprovados |
