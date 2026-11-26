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

## Status final — 2026-11-26

| Frente | Gate técnico/visual | Limites e estado de publicação |
| --- | --- | --- |
| ML-052 | CR e DA aprovaram o candidato cumulativo `2669ec2f809657dc309b591117ac1086b11e5853`; ajuste inicial e Guia estão documentados nos relatórios selecionados. | Reflow anterior equivalente a 200% não era zoom nativo; B7 verificou avisos e catálogo no Chrome a 200%. Sem validação de Setup instalado ou aceite manual global. |
| ML-053 | Levantamento dos 36 achados concluído; correções derivadas foram reconciliadas em ML-056/057 e cobertas pelo fechamento CR/DA do candidato `2669ec2f809657dc309b591117ac1086b11e5853`. | As 62 evidências privadas continuam locais e não foram adicionadas ao Git; cobertura e limites constam em `reports/ml053_coverage_checkpoint_2026-11-24.md`. |
| ML-054 | Núcleo CR `4999670`; integração B0–B6 aprovada em `604cad188d66918e30f3e06ac530a2f1c1fc01d9`; B7 visual fechada na DA e CR cumulativo em `2669ec2f809657dc309b591117ac1086b11e5853`. | +5 p.p. nas cinco regiões é sensibilidade, não campanha real; não alegar participação CPU real validada por essa simulação. |
| ML-055 | Backend e central receberam gates focais CR/DA; integração B0–B6 e fechamento visual B7 foram aprovados no candidato cumulativo `2669ec2f809657dc309b591117ac1086b11e5853`. | Sem ação no save real. Resultado integrado não altera limites nem requisitos de gameplay. |
| ML-056 | Critérios de apresentação/estado e dependências compartilhadas foram aprovados pelos gates CR/DA focal e pelo fechamento B7 no mesmo candidato cumulativo. | Consultas mantêm a autoridade dos serviços; dados ausentes não são tratados como zero e ações de consulta não resgatam nem alteram recursos. |
| ML-057 | Shell, navegação, layouts e fluxos receberam aprovação CR/DA focal; B7/P01–P03 fechados no candidato cumulativo `2669ec2f809657dc309b591117ac1086b11e5853`. | Teste de cache contrato-only posterior `51e88d4be85a84067f302fb5a97f5ff24cba59ff`: suíte Node 81/81, zero skips. |
| Versão/publicação | `DEV-v0.11.0` publicada como prerelease após aprovação CR/DA do pacote. | PR #25 foi integrado em `2cadd4451eaee5d1a122743338b81d0e80c62146`; tag `DEV-v0.11.0`, workflow `45897483540` e verificação dos assets estão registrados em [`reports/dev_v0.11.0_release_verification_2026-11-26.md`](../reports/dev_v0.11.0_release_verification_2026-11-26.md). Nenhum Setup foi aberto/instalado localmente e nenhum save real foi alterado. Aceite manual do usuário é posterior à entrega. |

## Registro de publicação — DEV-v0.11.0 — 2026-11-26

O pacote ML-052–057 foi publicado como prerelease `DEV-v0.11.0` em 2026-11-26 às 21:23:32 UTC. PR #25 foi integrado no merge `2cadd4451eaee5d1a122743338b81d0e80c62146`; a tag aponta para esse merge. O workflow de release `45897483540` concluiu com sucesso e os smokes do pacote, campanha e launcher passaram. A verificação criptográfica, hashes dos três assets, escopo e limites constam no [relatório sanitizado de verificação](../reports/dev_v0.11.0_release_verification_2026-11-26.md).

ML-052–057 estão entregues. A validação manual do usuário pode ocorrer posteriormente e não é pendência de desenvolvimento. A publicação não envolveu abrir/instalar o Setup nesta máquina nem operar ou alterar um save real. Os registros de ML-028, ML-045 e BUG-014 não recebem aceite novo neste pacote; o aceite de BUG-013 permanece preservado.

## Estado no início do pacote (registro histórico)

O estado abaixo foi capturado antes do fechamento B7 e da publicação; é preservado para cronologia e não substitui o status final de 26/11 registrado acima.

### Decisão de conteúdo e participação CPU

Pré-flight CR no baseline confirmou que, em quatro templates do pool nos estágios 50/100, três são inviáveis para todas as CPUs recém-semeadas; exigem equipamento que o modelo atual não obtém. Essa amostra não mede CPUs evoluídas. Na ML-055, não criar um sistema novo de equipamento NPC nem relaxar requisitos: escolher conteúdo ativo com loot que pelo menos um ator real nativo tenha capacidade de cumprir. Na região natal, manter o teto de progressão do jogador e considerar a união de capacidades jogador/CPU; não excluir desafio viável para o jogador só por ser inviável para a CPU. Em regiões externas, usar a progressão das próprias guildas CPU, não a guilda do jogador como teto global. A ocupação momentânea não define capacidade potencial de conteúdo; disponibilidade real define o agendamento.

Nas novas regras, remover o pré-sorteio de 25% de entrada CPU e priorizar a avaliação de portal viável, mantendo uma entrada por guilda/evento e combate real. Persistir motivos objetivos de não participação. Portais podem terminar depois do fechamento da Vigília/janela se iniciados no prazo, sem antecipar resultados/XP e com equipe ocupada até a conclusão real. Equivalência visita/ausência/retry é requisito. A ausência de encontro viável bloqueia geração com diagnóstico, sem consumir falha do stack. Implementação desta decisão pertence a ML-055, em SHA separado da fórmula de ML-054.

| Frente | Estado | Próximo gate |
| --- | --- | --- |
| ML-054 | Núcleo aprovado pelo CR: `4999670`; integração técnica B0–B6 aprovada em `604cad1` | 45 testes independentes, migração/legado/retry e oito casos da simulação reproduzidos. +5 p.p. nas cinco regiões é sensibilidade, não campanha real; janela perdida depende de presença ilustrativa. B7 visual integrado pendente; sem publicação |
| ML-053 | Levantamento concluído; validação derivada reconciliada com ML-056/057 | 36 achados/oportunidades e 62 evidências privadas locais; cobertura e limites em `reports/ml053_coverage_checkpoint_2026-11-24.md`. B7 visual integrada ainda pendente |
| ML-052 | Aprovada por CR e DA: núcleo `897fde9`, ajuste `64d6d34f7f2482938fb304a5d6e60e5c93016210` | Relatório `reports/ml052_da_64d6d34_2026-11-24.md`; cinco larguras e reflow equivalente a 200%, não zoom nativo WebView2. Sem aceite manual ou publicação |
| ML-055 | Backend aprovado pelo CR em `043cb5eceac1bc160c76350cf3a4b628bac2f200`; central aprovada por CR e DA em `5fe567968fb53803e3873b7bb5c68f94266b1fa6`; B0–B6 integrado aprovado pelo CR em `604cad1` | CR repetiu 73 Python + 12 JS + 1 smoke na central. DA fechou estados, foco, seleção, expiração externa com contagens 0/0 e retry em `reports/ml055_da_5fe5679_2026-11-25.md`. B7 visual integrado ainda pendente; sem build/instalação/publicação |
| ML-056 | Implementação e retestes focais concluídos; integração técnica B0–B6 aprovada em `604cad1` | B7/zoom visual integrado aguarda autorização da ferramenta. Não publicado nem aceito manualmente |
| ML-057 | Implementação e gates focais concluídos; integração técnica B0–B6 aprovada em `604cad1` | B7/zoom visual integrado aguarda autorização da ferramenta. Não publicado nem aceito manualmente |
| Publicação | Não iniciada | Concluir B7/zoom integrado e demais gates de aceite antes de tag/build/publicação |

## Histórico de acompanhamento - 2026-11-25

Os registros desta seção descrevem o estado conhecido em 25/11 e checkpoints anteriores. Pendências ali anotadas foram atualizadas pelo fechamento CR/DA e pela publicação registrados acima.

### Reconciliação posterior de integração

- **Estado naquele checkpoint:** CR aprovou B0–B6 cumulativo em `604cad188d66918e30f3e06ac530a2f1c1fc01d9`, sem achados técnicos abertos. A corrida de navegação foi corrigida em `8bead5bc6e2670815a185fabe7341f29d1ba050e`; CR repetiu 80 testes JavaScript, quatro casos adicionais e jornada de 16 registros, além de conferir por HTTP o asset com cache versão 10. Grupos anteriores intactos foram reconciliados por fonte, sem alegar repetição integral simultânea de todos os testes.
- A passagem visual integrada B7/zoom real continua aguardando autorização obrigatória da ferramenta. Retestes focais não substituem essa etapa. A versão 0.11.0 e changelog foram preparados em `ad381ab230a5b10aeb6c7169d5b0d3dc9ba6c0e3`; o checkpoint documental está sendo fechado em commit separado. Não houve tag, build, instalação, push ou publicação. Os pontos seguintes preservam a cronologia da integração e não reabrem achados já corrigidos.

- F26 recebeu correção de Progresso da Guilda em `bc654a00d9e233deb7066584262845e65e96a53f` e restauração do requisito base em `78d43630fe04799dd1f6f0bb4538969a79d89c75`, aprovada tecnicamente pelo CR. O recorte visual de conteúdo e estados foi verificado pela DA.
- Os quatro resíduos de Inventário/Mercado/Docas e a apresentação canônica F33 foram fechados nos recortes CR/DA em `0434c60fa1ecca9c442200ef18c7dac49d3a7027`. A interferência entre os timers da Oficina e do preparo regional foi corrigida em `2374edccdd7e15e9660bb33d47d29077e772e3d1`, com complemento de teste `635156b630f3334c2823ed8b8b566721b530c064`, e aprovada pelos dois revisores.
- F12 recebeu aprovação técnica em `50b9abc7ee73324c60225df2fdb37c0e204d1dcc`; a DA complementou livre/catálogo indisponível/sem trabalhadores, reutilizando os estados e polling de F20. As últimas telas receberam três ajustes focais de acessibilidade em `0ba1066107ab660c504282d9bb85e5538c6bd273`; o reteste focal passou, mas a passagem visual integrada continua pendente.
- A primeira integração CR em `78d43630` executou 269 unittest (261 aprovados), 75 JavaScript aprovados e seis funções Releases (cinco aprovadas), sem skips. Sete falhas de política, um contrato do smoke e um contrato Releases foram corrigidos sem alterar regras em `0907cae150dd8e48e8423e2aea394248bade2880`; CR repetiu 13 testes de política, um smoke HTTP completo e seis funções Releases, todos aprovados. Esses retestes não apagam o resultado histórico nem aprovam o pacote inteiro.
- Na primeira passagem foi aberto o P2 funcional de navegação: uma resposta GET atrasada podia sobrescrever a Central solicitada posteriormente. A correção e o reteste estão registrados no estado mais recente acima. A jornada visual integrada/zoom real de 200% aguarda autorização obrigatória da ferramenta na conversa DA; não substituir essa evidência por reflow equivalente nem contornar a autorização.
- Versão definida pela coordenação: `0.11.0`, preparada em commit separado de fonte/changelog/testes `ad381ab230a5b10aeb6c7169d5b0d3dc9ba6c0e3` e aprovada focalmente pelo CR, sem achados. Guia/exportação, página `/updates`, `/updates/check` e atualizador passaram 7 + 1 + 2 testes. A preparação não autoriza tag, build, instalação ou publicação antes dos gates integrais. Os itens abaixo registram checkpoints anteriores, não o estado final mais recente.

- Meta global permanece ativa na conversa coordenadora. DEV, DA e CR trabalham na mesma branch; nenhuma aprovação focal encerra a entrega global.
- ML-056 F08–F11: composição dos gates em `99cd2a954162d809ee7e50d82495d07c10bdee5f`, `4c1c0463497c8d3f994a0f8604fe7c809bef000e` e `5508c088e52252818392107a681249a44c731b5e`. Incluem saldo conhecido/ausente, identidade de classe, hierarquia de ações, detalhes de equipamento responsivos e resultados recolhidos. Aprovações não substituem regressão de integração.
- ML-056 F18/F20: gates CR/DA fechados no conteúdo final `f65297912c5328360f4122dabe291ee4a73111d3`, incluindo rótulos PT-BR e atualização coerente dos estados de coleta. F12 reutiliza somente esses critérios já cobertos; o recorte complementar foi concluído e está reconciliado em B0–B6.
- ML-056 F33: correção read-only do Códex aprovada tecnicamente em `dddf228669a4fcbd38bab1668586ce0ec80d1ee8`; mantém lore personalizado e dados persistidos intactos. Inspeção visual deve integrar o gate final do lote.
- Registro histórico: o candidato `54b6955d108b6c415a4a95745cb07935aef95c25`, base `9a3d1210b34a206a2cd779ab7ea3870d9dedf60e`, foi encaminhado ao CR e à DA com os resíduos da Oficina/Desmontagem e Inventário/Mercado/Docas. Naquele ponto, DEV havia informado 69 testes Node, 73 Python e um smoke HTTP sintético, com retestes pendentes. A revisão posterior foi reconciliada e aprovada no B0–B6 cumulativo `604cad1`.
- Registro histórico: naquele checkpoint as fatias independentes ainda eram Construções, Reset, Troca de Classe, Profissões, Códex e Coleta; esses itens foram posteriormente implementados e reconciliados na aprovação técnica B0–B6. Preservar regras econômicas e autoridade dos serviços.
- As evidências atuais usam perfis descartáveis. Medições de reflow equivalente a 200% não são zoom nativo WebView2. Não houve nova operação no save real, build de distribuição, instalação, push ou publicação.
