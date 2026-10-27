# Gates de revisão — Guild Idle Manager Desktop Offline

Este documento é o checklist independente da conversa principal. A fonte do escopo é `docs/GDD_DESKTOP_OFFLINE.md`. Nenhuma etapa é aceita apenas porque o código compila ou porque os testes antigos passam. Cada gate exige evidência no estado atual da branch `feature/desktop-offline`.

## Regra de operação

- Pasta única: `C:\Users\vitor\Guild Idle Manager\App GIM`.
- Sem worktrees, novas branches de execução ou mudanças na pasta web original.
- Commits por assunto, com arquivos limitados ao dono da tarefa.
- DA: `docs/art_direction/`, `design/`, `app/static/assets/desktop/`.
- DEV: código, testes, scripts de build e documentação técnica; não alterar assets da DA sem revisão.
- A conversa principal revisa diff, execução, dados e resultado visual. Pendência retorna ao autor da etapa; não é aceita por promessa de correção futura.

## Gate DA — Identidade visual

- [ ] Guia de identidade define paleta variada, tipografia local/licenciada, grid, espaçamento, estados, raridade e acessibilidade.
- [ ] Uso real da skill `imagegen` comprovado por assets bitmap entregues, não apenas por briefing ou mockup.
- [ ] Assets cobrem as superfícies prioritárias do jogo e possuem nomes, dimensões, manifesto e fallback.
- [ ] Preview desktop e janela estreita podem ser abertos localmente e mostram interface legível, sem sobreposição.
- [ ] Assets funcionam offline, sem CDN, têm pesos razoáveis e licença/proveniência registrada.
- [ ] A direção preserva os ícones existentes que ainda servem e melhora o que for necessário; não há regressão de identificação de classe, item ou construção.
- [ ] A conversa principal visualizou os previews e informou ao usuário os caminhos exatos para vê-los.

## Gate 1 — Core offline e campanhas

- [ ] App novo cria e abre campanha SQLite sem PostgreSQL, `.env` ou login.
- [ ] Duas campanhas têm guildas, recursos, mercenários, itens e progresso isolados.
- [ ] `campaign_metadata`, preferências de tutorial/confirmação e identificação da campanha persistem entre aberturas.
- [ ] Chaves estrangeiras, transações, cascatas e locks possuem comportamento compatível com SQLite.
- [ ] Missão, masmorra, loot, inventário, contratação e construções continuam respeitando pré-condições e atomicidade.
- [ ] Alembic/estratégia de schema local é versionada e não executa SQL exclusivo do PostgreSQL.
- [ ] Seeds de conteúdo são aplicadas por versão; segundo carregamento não duplica nem sobrescreve estado.
- [ ] Modo web anterior ainda inicia ou há justificativa explícita/testada para mudança inevitável.
- [ ] Testes novos usam diretórios temporários e não escrevem em guildas reais; suite anterior continua verde.
- [ ] Relatório DEV lista commits, arquivos, comandos, resultados e riscos conhecidos.

## Gate 2 — Janela, save e relógio

- [ ] Aplicativo inicia e encerra FastAPI local junto de uma janela própria; servidor escuta apenas em loopback.
- [ ] Nova campanha/continuar/renomear/exportar/importar/excluir funcionam com confirmação e tratamento de erro.
- [ ] Save, backups, logs e âncora de tempo ficam fora da pasta de instalação e fora do Git.
- [ ] Migração de save faz backup prévio; falha não destrói o save original e oferece recuperação.
- [ ] Aplicativo aberto não concede idle; retorno de período fechado concede uma vez, respeitando mínimo e teto atuais.
- [ ] Relógio monotônico é usado durante execução; retrocesso, salto, corrupção da âncora e crash têm testes determinísticos com relógio injetado.
- [ ] Timers e coleta manual de missão, masmorra, mercado, taverna e ferreiro seguem as regras existentes.
- [ ] Launcher DEV usa o checkout em `App GIM`, sem reinstalação e sem instalar dependências/migrar PostgreSQL a cada inicialização.
- [ ] Relatório DEV lista commits, arquivos, comandos, resultados e riscos conhecidos.

## Gate 3 — Build DEV e regressão final

- [ ] Executável/instalador Windows inclui Python, templates, CSS/JS, assets, JSON de dados e migrations necessários.
- [ ] Smoke test em ambiente limpo sem Python, PostgreSQL, `.env` e rede.
- [ ] Atualização por instalador preserva saves e permite migrar/restaurar versão anterior.
- [ ] QA manual registra ao menos um fluxo de cada sistema listado na seção 13 do GDD; falha/sucesso de loot são verificados.
- [ ] Interface integrada à nova DA é responsiva, tem imagens reais e mantém navegação fluida em janelas desktop e estreitas.
- [ ] Testes automatizados atuais e novos passam; gaps são explicitados, não escondidos por skips silenciosos.
- [ ] Pacote não contém senhas, `.env`, arquivos de conta de teste, saves do usuário nem logs pessoais.
- [ ] README contém comandos reais para DEV, build, instalação, backup e recuperação.
- [ ] Branch só é integrada/fechada depois de todos os gates aceitos e GDD auditado item por item.

## Registro de revisão

Para cada retorno de DA ou DEV, registrar na conversa principal:

1. Revisão/commit examinado.
2. Arquivos e superfícies inspecionados.
3. Comandos de teste, resultado e ambiente.
4. Evidência visual/runtime quando aplicável.
5. Achados com gravidade e responsável.
6. Decisão: aprovado, devolver para correção, ou bloqueado com motivo verificável.

Este checklist não substitui o GDD nem os testes de regressão; serve para tornar explícito o padrão de aprovação.
