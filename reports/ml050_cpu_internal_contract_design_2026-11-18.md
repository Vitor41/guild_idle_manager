# ML-050 — desenho da contingência interna para CPU

## Persistência e isolamento

- Reusar `RegionalOffer`; não criar tabela nem migração de schema.
- Persistir no máximo um registro por região e ciclo com `offer_type="cpu_internal"`, `status="cpu_internal"` e slot reservado 1. A unicidade existente por ciclo, região, tipo e slot limita duplicatas e torna retries idempotentes.
- Criar o snapshot a partir de um `MissionTemplate` ativo, mantendo todos os requisitos, duração, chance e recompensas reais. Não reescrever ofertas públicas, snapshots ou planos anteriores.
- Filtrar esse tipo na consulta do quadro público e rejeitá-lo em uma validação central de elegibilidade de oferta nas rotas de cotação, preparo, início e API.

## Geração e uso

- A elegibilidade ao fallback é fixada individualmente no início do plano de cada CPU, após eventual contratação normal: a CPU precisa ter zero atividades públicas viáveis nesse instante. Uma CPU que começa com uma ou mais atividades públicas viáveis não passa a ser elegível depois de executá-las ou esgotar sua janela no mesmo ciclo.
- Antes dos planos CPU da região, avaliar ofertas públicas com o helper real de seleção de equipe e janela de conclusão. Ignorar estados CPU inativos ou sem elenco ativo; não exigir ação deles.
- Só criar o registro se houver ao menos uma CPU ativa com elenco que não consiga iniciar nenhuma atividade pública viável. Escolher primeiro, de modo determinístico, a CPU bloqueada de menor nível/estágio; em seguida selecionar entre templates ativos que ela realmente consegue cumprir. Se nenhuma equipe/template passar pelos requisitos reais, não criar oferta.
- Usar RNG derivada separadamente de campanha, ciclo, região e versão das regras para desempatar templates e rank. Esse RNG não consome nem altera o sorteio público ou a RNG normal do plano CPU.
- Cada CPU elegível só considera uma cópia transitória do snapshot interno, no máximo uma vez por ciclo. A cópia usa o fluxo normal de horário, equipe, chance, recompensa e progressão; seu estado mutável não consome o registro compartilhado, permitindo reuso por outra CPU elegível. Nenhum orçamento, contratação ou crédito de XP extra é criado.
- Marcar a ação interna no plano para que o ledger de portal/rebelião a ignore. Não permitir participação do jogador por ID conhecido ou forjado.

## Regressões previstas

- Tabela real nos cortes 14/15, 24/25, 29/30, 49/50 com CPUs 1/2/3/5: elegibilidade fixada no início do plano; uma CPU que inicia com atividade pública viável nunca usa fallback no ciclo, mesmo após concluir ações públicas; CPU que inicia com zero pode usar uma única vez.
- Requisitos, equipe, duração e recompensa vêm do template ativo sem relaxamento; roster ausente/inativo não obriga ação.
- Um registro por região/ciclo, determinismo, idempotência em retry e isolamento entre campanhas/regiões.
- Uma mesma oferta interna é reutilizável por mais de uma CPU inicialmente elegível, sem mutação do registro persistido nem repetição pela mesma CPU no ciclo.
- O quadro e as rotas/API do jogador não expõem nem aceitam o registro; ledger de rebelião não o conta.

Este desenho autoriza implementação local sem mudança de schema. A evidência de elegibilidade em `ml050_cpu_band_eligibility_2026-11-17.md` e seu JSON são baseline imutável; não repetir a campanha longa 5 × 100.
