# ML-057 — fatia restante, DA no cumulativo d44be947

> Cópia sanitizada para versionamento em 2026-11-26. Evidências sintéticas locais, scripts, resultados brutos e capturas permanecem fora do Git; parecer, medidas, SHAs, falhas e limites foram preservados.

Data: 2026-11-25. Candidato `d44be947dce5aa38cd918e44943220a47dbd94c0`, cumulativo sobre a implementação restante `0f3f6e5f43459af7424b2aec206d9a005969d02d`; base anterior `4daf88e`. Branch `feature/anomalies-ui-audit`.

**Não aprovada esta fatia: quatro P2 medidos abaixo; F14/F16/F19 bloqueados pelo P1 de contexto/request da macro já informado pelo CR.** A correção separada dos dois P2 antigos F03/F06 foi validada em outro relatório. Nenhuma aprovação global de ML-056/057 ou aceite do usuário.

## Achados consolidados

| ID / prioridade | Local e reprodução | Medida / evidência | Aceite focal |
| --- | --- | --- | --- |
| DA057-R1 · F30 · P2 | `app/static/css/main.css`, `.classes-guide-index` sticky e `.guide-section` scroll-margin; /classes → Habilidades no índice, 1440 CSS px, esperar estabilização | Índice top 84 e bottom **142 px**; título de Habilidades começa em **118,78 px**, encoberto em cerca de 23 px. Seção top 95,78, foco guia-habilidades. Medições e captura sintéticas locais do destino. O offset considera topbar, mas não todo o índice fixo acima do destino. | Título e foco da seção visíveis abaixo da soma real de topbar/índice e respiro, sem valores fixos incompatíveis com quebra/zoom. Retestar âncora em ampla e reduzida/reflow. |
| DA057-R2 · F31 · P2 | `app/static/css/main.css`, `.tier-guide-grid` auto-fit/minmax(250px,1fr); /tiers em 1440 | Largura útil **1081 px**; seis entradas renderizadas em **4+2**, colunas 259,75 px. Ocorre nos dois grupos de raridade. Critério aprovado pede 3×2 a partir de 900 px úteis. Em 980, largura útil 899 px também produz 3 colunas, em vez das 2 previstas entre 560–899. Evidência sintética local de layout/captura. | Aplicar grade equilibrada conforme largura útil (3/2/1), mesma ordem e sem cortar nomes/descrições; não ajustar por viewport ignorando sidebar/padding. Não mudar raridades. |
| DA057-R3 · F35 · P2 | `app/templates/tutorial/index.html`, `.tutorial-actions form[action="/tutorial/decline"] > button.text-button`; cascata CSS do botão | **Pular tutorial mede 36 px de altura nos 26 casos**: 13 etapas × 390/1440. Outros controles não foram usados para encobrir essa medida. Ícones de todas as etapas carregaram e não houve overflow. Evidência sintética local cobre passos/larguras, alvos e foco. | Alvo real ≥40×40 CSS px, foco legível, sem executar pular/concluir ao consultar. Verificar a regra vencedora da cascata; min-height textual no arquivo não basta. |
| DA057-R4 · F36 · P2 | `app/templates/updates.html`, handlers inline de `[data-check-local-update]` e ciclo parcial de `app/static/js/main.js` | Direto: clique faz uma consulta /updates/check, mostra loading e termina em “Checkout local já está nesta versão.”. Entrar /classes→/updates pelo handler parcial real: mesmo documento, botão visível, mas clique não faz consulta e mantém “Verificação local; nenhuma conexão remota será aberta.”. Contador antes/depois permanece **1→1**; disabled=false. Evidência sintética local de fluxo direto/parcial. | Inicializar Verificar no root novo de forma idempotente após navegação parcial; loading/final/erro reais e uma consulta por clique, sem instalação. Preservar as restrições de origem/caminho já aprovadas em F34. |

As quatro linhas correspondem a critérios aprovados, não novas preferências estéticas. Não reclassificam conteúdo nem propõem terceiro lote.

## Bloqueio conhecido do CR — não duplicado como novo achado DA

GET /regional na fixture com ícone real de classe retornou HTTP 500; log termina em `KeyError: request` no url_for chamado pela macro regional_offer_actions. O CR já informou que a importação da Vigília está sem contexto. O harness não removeu ícone nem substituiu a macro para obter aprovação.

Consequências: F14 (grade de ofertas), F16 (modal/preparados/reforços) e F19 (relatório da mesma rota) **não receberam gate visual**. O erro do primeiro script ao procurar link regional em documento de falha foi consequência desse P1, não prova de ausência de conteúdo. Próximo SHA deve renderizar com ícone real antes da captura.

## Matriz por Fxx desta fatia

| Fxx | Resultado / evidência / limite |
| --- | --- |
| F14 | **Bloqueado pelo P1.** Não se promove inspeção estática da grid a aprovação 3/2/1. Medir largura útil e colunas quando a rota voltar. |
| F16 — modal ML-057 | **Bloqueado pelo P1.** Header/fechar sticky, scroll, Escape/retorno e acesso às ações ainda não observados nesta versão com ícone real. Não remover o dado para medir. |
| F16 — seleção/equipe compartilhada ML-056 | **Setup autoritativo pronto, visual pendente.** POSTs prepare reais aceitaram contrato/dungeon/boss; respostas 303 com mensagem de preparo. IDs 43/53/56 e membros 17/18/19 nesta execução; snapshots preservados no arquivo local. Factory admite running/ready/unavailable em banco. Não foi possível demonstrar grupos/selos, seleção/refoço, incompatibilidade, preservação de IDs no envio ou resumo no DOM; não aprova ML-056 restante. Conferir também regra aprovada: selo Reforço somente quando selecionado. |
| F17 | **Passou no recorte de tabela regional.** 390 e reflow: overflow apenas no wrapper, nome/guilda próprios continuam fixos à esquerda ao rolar 300 px (deriva 1,5 px de borda); Sua guilda visível. Em 1440 a tabela de largura 1069 cabe sem scroll. Não se recalculou ranking/pesos; tabela principal da Vigília segue bloqueada pelo P1. |
| F19 | **Bloqueado pelo P1.** Seed SQL de RegionalCycleRegion com antes/depois, um plano com campos None e outro com zeros persistidos, sem simular fechamento real. Render de métricas/missing≠0 ainda não validado. Não dizer “sem achados” nesse fluxo. |
| F30 | Conteúdo/índice/retornos presentes nas seis configurações, sem overflow; **reprovado** pelo título oculto ao usar índice sticky, R1. |
| F31 | Seis entradas e rótulo não duplicado, equipamento com apresentação curta; **reprovado** por 4+2 em ampla, R2. |
| F32 — navegação | **Passou no recorte observado.** category=class e trail=collection preservados no detalhe e retorno; retorna ao card codex-entry-9, foco no card, top 99,16 px. Não houve resgate. Não aprova apresentação/estados de conquistas de ML-056. |
| F35 | 13 etapas com ícone carregado e sem overflow em 390/1440; GET replay sem concluir/pular; **reprovado** pelo alvo Pular de 36 px, R3. |
| F36 | Direto local: versão 0.10.0, loading→resultado, uma consulta read-only, sem instalação. Componente empacotado controlado: Canal stable, provedor subordinado e botão Verificar 40 px. **Reprovado** na entrada parcial local, R4. Não se testou serviço remoto de releases nem instalação nativa. |

## Superfície, controles e proveniência

24 casos independentes de layout: detalhes da região natal, Classes, Raridades e Códex × 390/980/1100/1101/1440 e 720×450 CSS px com escala 2. **Nenhum overflow horizontal global**. Reflow 720 equivale a 200% numa superfície física 1440×900; não é zoom nativo WebView2. O tutorial teve 26 casos adicionais em 390/1440, todos com imagem naturalWidth>0 e sem overflow.

Campanha temporária da seed desktop smoke + acervo/preparo da preparação anterior. A primeira tentativa de preparo escolheu oferta externa e foi recusada pelo serviço. O harness foi corrigido para selecionar região natal e templates de teste elegíveis; nenhum código/regra do produto foi alterado. Os três POSTs reais passaram. Isso prova setup e persistência, não gate visual ou balanceamento natural da campanha. O encerramento da tentativa rejeitada deixou temporário bloqueado durante cleanup; processo encerrou e nenhum arquivo do usuário foi apagado/forçado.

F19 usa dados históricos explicitamente semeados em SQL para apresentação, não um fechamento de ciclo executado. Não foram fabricados relatórios de ausência.

A entrada parcial de Atualizações foi acionada pelo listener real de main.js com data-async-navigation colocado no link apenas no DOM sintético, conforme método já documentado em F34. Documento preservado. O acesso direto foi testado separadamente. A superfície empacotada usa o template candidato, contexto de canal stable controlado e resposta de consulta sintética; não troca sys.frozen nem acessa GitHub. Nenhuma origem externa foi usada para a investigação.

## SHA e arquivos fixados

Candidato cumulativo d44be947. Diretório conserva 0f3f6e5 no nome por origem histórica. Templates e assets CSS/JS são servidos por sobreposição read-only do git show do SHA, sem checkout/reset ou edição do produto. Isso também impediu que mudanças em andamento do DEV em regional/index.html e updates.html fossem promovidas a candidato testado. Conteúdo HTTP de main.css, desktop-evolution.css, desktop-theme.css, main.js e regional-supply.js coincide byte a byte com os blobs do SHA; manifesto local de hashes registra a comparação. Serviço regional e rota Updates não apresentaram diff nas conferências.

| Arquivo | Blob do candidato |
| --- | --- |
| `app/static/css/desktop-evolution.css` | `116756c2772be4fcdc50ab1be30748eecd2501c7` |
| `app/static/css/desktop-theme.css` | `14cfa1733ee7538d222c0cf2dbc4f23151af963b` |
| `app/static/css/main.css` | `faa820490c535150bfbc2c41f1ca3113bad59789` |
| `app/static/js/main.js` | `d5026cbae6af8fb7ff6b6e0c0f9e20604a669a01` |
| `app/templates/classes/index.html` | `c29ad99665b782b8ab1e68fc7cc4fad9195dd19e` |
| `app/templates/codex/index.html` | `eafcf66d3b3d798bc67092f31217b30352724ba7` |
| `app/templates/components/regional_offer_actions.html` | `0a662b51ad007f198a36b3bcfc836b4f02cc8888` |
| `app/templates/regional/index.html` | `c567849335a5990566c50da6ed84abf11d17a718` |
| `app/templates/tiers/index.html` | `95314bd5bcb3b6c9ea1cc2108f4c5a626920e5e3` |
| `app/templates/tutorial/index.html` | `ca7773ce3423e1c4d544d0aaa6ba5987feace965` |
| `app/templates/updates.html` | `57ad5ca508a281fc7b1270fbe1d3de999063cf00` |

## Artefatos e próximo gate

Evidências sintéticas locais preservam 24 casos de layout/âncoras/tabelas, 26 passos/larguras de Tutorial e Updates, retorno do Códex, snapshots preparados na cópia e hashes dos blobs HTTP do candidato. Paths, scripts, resultados brutos e capturas permanecem fora do Git.

Próximo SHA: corrigir P1 da macro e R1–R4; retestar focalmente esses pontos e completar F14/F16/F19 com dados já preparados. Não repetir telas independentes intactas nem os 13 passos em todas as larguras sem mudança que justifique. Nenhuma edição de runtime, commit, instalação ou uso do save real; sem aprovação dos lotes globais. CR e aceite do usuário independentes.
