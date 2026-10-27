# GDD — Guild Idle Manager Desktop Offline

**Status:** especificação para implementação DEV  
**Plataforma inicial:** Windows 10/11 x64  
**Modo inicial:** campanha individual offline  
**Data:** 26/10/2026

## 1. Resumo do produto

Guild Idle Manager Desktop é a versão instalável para PC do jogo atual. Deve abrir em janela própria com aparência de aplicativo, reutilizar a interface web e as regras de jogo existentes, funcionar sem internet e não exigir que o jogador instale Python, PostgreSQL ou ferramentas de desenvolvimento.

O jogador inicia uma campanha local, administra uma guilda, salva automaticamente e pode continuar ou começar outra campanha. Login, cadastro, sessão web, multi-tenancy por usuário, painel admin e recursos online não fazem parte desta primeira versão.

Este GDD orienta uma implementação em até três fatias de trabalho. A prioridade é preservar o conteúdo e as regras existentes; balanceamento e refinamento do jogo são trabalho separado, exceto quando uma incompatibilidade bloqueia a versão desktop.

**Checkout de implementação:** `C:\Users\vitor\Guild Idle Manager\App GIM`. O projeto web na pasta-pai é referência histórica e não deve receber alterações desta entrega. Todos os comandos abaixo são executados dentro de `App GIM`.

## 2. Referência e auditoria do projeto existente

O levantamento foi feito na raiz `C:\Users\vitor\Guild Idle Manager`. A pasta contém a aplicação em `app/`, documentação e roteiros em `app/docs/`, migrations em `alembic/`, ferramentas e relatórios de QA, assets, testes e o inicializador web `Iniciando_venv.bat`.

Inventário observado nesta revisão: 17 arquivos Python em `models`, 24 em `routes`, 40 em `services`, 20 migrations e 6 arquivos de teste. As contagens incluem arquivos `__init__.py`; são uma fotografia do estado atual e devem ser confirmadas pelo agente antes de alterar a estrutura.

### 2.1 Fontes de contexto consultadas

- `README.md`, `requirements.txt`, `alembic.ini` e `Iniciando_venv.bat`.
- `app/main.py`, configuração, conexão, dependências, autenticação, guilda, sessão e progresso offline.
- Estrutura dos módulos de `models`, `routes`, `repositories`, `services`, `templates`, `static`, `seeds` e `data`.
- Roteiros de MVP, documentos de produto, modelo de dados, loop de jogo, balanceamento, classes, UX e QA em `app/docs/`.
- Os arquivos `Melhorias_para_PRD.md`, `Melhorias_para_PRD_2.md`, `Melhorias_para_PRD_3_Masmorras_Chefes.md`, `PRD-050-QA-MANUAL.md`, relatórios de QA/balanceamento e scripts de simulação.
- Migrations existentes e padrões de testes automatizados.

Este documento não afirma que cada linha dos muitos milhares de linhas de conteúdo foi revisada manualmente. É uma especificação baseada no inventário completo, nos contratos/documentos centrais e na inspeção dirigida dos pontos arquiteturais que afetam desktop, saves e relógio. O agente de implementação deve executar os testes e buscas indicados antes de fechar a entrega.

### 2.2 Sistemas de jogo que devem ser preservados

O desktop deve reutilizar, sem remover mecânicas existentes:

- Guilda, tesouro e construções, incluindo Alojamento, Campo de Treino, Ferreiro, Armazém, Escritório, Exploradores, Taverna, Mercado e Docas.
- Mercenários, raridades, classes, progressão, atributos, poder, equipamento, slots, profissão, contratação e demissão.
- Missões comuns, coleta, missões longas, expedições, multiplicadores, timer, resultado e coleta manual.
- Masmorras e chefes, grupos, recomendações, bloqueios de entrada, timers, drops e coleta manual.
- Inventário acumulável, equipamentos únicos e RNG por instância.
- Taverna, contratação em massa, ofertas especiais e rotação.
- Ferreiro, receitas/crafting, refino e desmontagem, respeitando os desbloqueios e custos atuais.
- Mercado, vendas temporizadas e coleta individual/em lote; Docas e rotação de mercadores.
- Skills, conquistas, coleção/Codex, tutorial, guia do jogo e histórico de resultados.
- Interface medieval/fantasia, assets, identidade de raridade, ícones, navegação e idioma PT-BR.

As rotas de gameplay e os serviços existentes são o ponto de partida. Não reescrever a lógica em um segundo motor sem justificativa e testes de equivalência.

## 3. Decisões de arquitetura

### 3.1 Stack escolhida

- **Python:** runtime e regras do jogo.
- **FastAPI:** servidor local e rotas já usadas pela aplicação.
- **Jinja2:** renderização server-side das telas atuais.
- **SQLAlchemy:** models, consultas e transações.
- **Alembic:** evolução do schema local.
- **SQLite:** um arquivo local por campanha, sem processo ou instalação de banco.
- **pywebview:** janela nativa que carrega a aplicação local.
- **PyInstaller:** empacotamento do runtime Python e dependências.
- **Inno Setup** (ou ferramenta equivalente escolhida pelo agente): instalador Windows.

O `pywebview` oferece janela nativa para HTML e pode apontar para um servidor local. A documentação também descreve ponte JavaScript/Python e servidor HTTP integrado; para este projeto, preservar FastAPI/Jinja em uma URL local reduz a quantidade de UI que precisa ser reescrita. [Guia do pywebview](https://pywebview.idepy.com/en/guide/), [arquitetura do pywebview](https://pywebview.idepy.com/en/guide/architecture)

PyInstaller é a opção inicial para empacotar Python; cada plataforma precisa do seu próprio processo de build. [Manual do PyInstaller](https://www.pyinstaller.org/en/stable/usage.html)

### 3.2 Diagrama lógico

```text
GuildIdleManager.exe
  ├── Desktop launcher (pywebview)
  ├── FastAPI local, acessível somente em 127.0.0.1
  │     ├── Rotas HTML existentes
  │     ├── Serviços e regras de jogo
  │     ├── Repositories
  │     ├── Jinja2 + static/assets
  │     └── SQLAlchemy Session
  └── Campanha ativa: SQLite em LocalAppData
```

O servidor local não é um serviço público. Deve iniciar junto do aplicativo, escutar somente em loopback e encerrar ao fechar a janela. Não abrir porta na rede local nem exigir navegador externo.

### 3.3 Organização de código desejada

Preservar os diretórios atuais e adicionar uma camada desktop/configuração explícita:

```text
app/
  desktop/
    __main__.py          # ponto de entrada da janela
    launcher.py          # inicia servidor, aguarda healthcheck e abre janela
    paths.py             # diretórios de dados e recursos empacotados
  core/
    config.py            # configurações por modo (desktop/dev)
    clock.py             # relógio e política de anomalia
  database/
    connection.py        # engine/session configuráveis por campanha
    migrations/          # se a estratégia Alembic exigir localização própria
  models/ repositories/ services/ routes/ templates/ static/ seeds/
```

Evitar espalhar `if desktop` por regras de negócio. O modo da aplicação deve ser resolvido em configuração/entrypoint e dependências, não duplicado em cada serviço.

## 4. Campanhas e saves

### 4.1 Arquivos e local de armazenamento

Os saves não podem ficar dentro da pasta de instalação, do checkout de desenvolvimento ou da pasta temporária do empacotador.

```text
%LOCALAPPDATA%\GuildIdleManager\
  saves\<campaign-uuid>.db
  backups\<campaign-uuid>\...
  logs\app.log
  clock-guard\...
```

Cada campanha terá um UUID estável e um banco SQLite autocontido. O menu de campanhas descobre os saves, lê nome, data de criação e última atividade do metadata e oferece continuar, renomear, criar, exportar/importar e excluir com confirmação do sistema.

### 4.2 Dados de campanha

Criar uma tabela `campaign_metadata` com, no mínimo:

- `campaign_id` UUID/texto único;
- `campaign_name`;
- `created_at_utc` e `updated_at_utc`;
- `schema_version`/versão Alembic;
- `content_version`;
- `last_clean_shutdown_utc`;
- `last_session_state` ou marcador equivalente para recuperação;
- `save_format_version`.

A guilda passa a ser propriedade da campanha local, não de uma conta web. A decisão recomendada é adicionar `campaign_id` e a relação necessária para manter isolamento, removendo no modelo desktop a dependência obrigatória de `guilds.user_id`. Tabelas globais e por guilda atuais continuam com seus papéis conceituais.

Preferências que hoje pertencem ao usuário, como estado do tutorial e escolhas de “não perguntar novamente”, passam para configurações da campanha (`campaign_preferences` ou campos equivalentes). Mensagens de retorno idle devem ser entregues uma única vez após o carregamento da campanha, sem depender de cookie/sessão HTTP.

### 4.3 Integridade e recuperação

- Cada ação de jogo deve usar transação e confirmar estado antes de exibir sucesso.
- Habilitar chaves estrangeiras do SQLite e tratar corretamente conexões/threading do SQLAlchemy.
- Usar Alembic para alterações futuras; verificar a compatibilidade de cada migration com SQLite.
- Fazer backup rotativo antes de migração de save e antes de importação/substituição. Manter ao menos os três backups mais recentes por campanha.
- Exportar por mecanismo de backup do SQLite ou após checkpoint consistente; não copiar um arquivo aberto de forma ingênua.
- Validar integridade e versão antes de abrir um save. Se falhar, oferecer restauração de backup e nunca sobrescrever o arquivo danificado automaticamente.
- Atualização do aplicativo não apaga saves. Atualização de schema deve ser transacional, com backup restaurável.
- Toda mensagem de sucesso de uma ação deve vir depois do commit; erro deve reverter a transação.

**Pendência explícita para o Trabalho 2:** o Gate 1 cria um backup antes da migração de schema, mas ainda não testa nem garante restauração automática do arquivo original quando uma migration falha. Até concluir rollback/restauração e seu teste de falha, o backup é apenas uma cópia preventiva; não declarar recovery de migration como pronto.

### 4.4 Conteúdo e seeds

Hoje `app/main.py` executa no startup seeds globais, conteúdo massivo, refinamentos e balance passes. Essa execução recorrente é acoplamento importante: não deve continuar reescrevendo conteúdo em cada abertura do aplicativo.

- Criar uma campanha nova: aplicar migrations e aplicar o pacote de conteúdo inicial, versionado e transacionalmente.
- Abrir campanha existente: aplicar apenas migrations e transformações de conteúdo explicitamente versionadas para aquela campanha.
- Não reaplicar balance patches/seed que sobrescrevam estado salvo ou configuração da campanha sem uma migração identificada.
- Preservar a idempotência e as regras de não sobrescrever alterações do jogador/admin que estejam em dados persistidos.
- A campanha offline não deve expor `/admin` ao jogador. Ferramentas de conteúdo poderão existir somente em execução DEV, sob flag explícita e sem alterar saves silenciosamente.

Os modelos de conteúdo e os catálogos do jogo podem continuar no mesmo SQLite da campanha nesta primeira versão, simplificando portabilidade e exportação. Não introduzir um servidor de dados separado.

## 5. Migração do sistema web atual

### 5.1 O que é reaproveitado

- `models`, `repositories` e grande parte dos `services`.
- Rotas, templates Jinja, CSS, JavaScript, assets e manifestos de ícones.
- Catálogo de conteúdo, fórmulas de progressão e regras de gameplay.
- Scripts de simulação e QA, adaptando a configuração de banco quando necessário.

### 5.2 O que precisa mudar

1. **Configuração:** hoje `app/core/config.py` usa PostgreSQL como padrão e lê `DATABASE_URL`; no modo desktop, a URL deve ser montada a partir do caminho da campanha. Nenhum `.env` com segredo ou URL de banco pode ser requisito do jogador.
2. **Conexão:** `app/database/connection.py` hoje cria uma engine global para um único banco. A campanha ativa exige engine/session configuráveis e ciclo de vida que feche conexões corretamente ao trocar campanha/encerrar.
3. **Alembic:** `alembic/env.py` aponta para `settings.database_url`, mas as migrations existentes não devem ser presumidas portáveis. Criar baseline/cadeia desktop apropriada ou reescrever migrations compatíveis sem perder a cadeia web; a decisão deve manter o modo atual web operável durante o desenvolvimento.
4. **PostgreSQL específico:** a busca encontrou lock `pg_advisory_xact_lock` em `mission_service.py`, índice parcial com `postgresql_where` em `salvage_service.py` e SQL `ON CONFLICT` em migration de recursos. Substituir por abstrações/estratégias portáveis para SQLite ou por alternativas com semântica equivalente e testes concorrentes.
5. **Autenticação:** remover do fluxo de campanha login, cadastro, logout, usuários, admin e `SessionMiddleware` como requisito. Não simular conta fictícia; criar/selecionar campanha é o fluxo de entrada.
6. **Resolução da guilda:** hoje `get_current_user` resolve `user_id -> guild`. No desktop, uma dependência `get_current_campaign` resolve a campanha ativa e sua guilda, sem receber `guild_id` confiável do frontend.
7. **Telas e rotas:** `/`, `/login`, `/register`, `/logout`, sessão web e criação inicial de guilda são substituídos pelo menu de campanha. Fluxos de gameplay devem continuar disponíveis após carregar uma campanha.
8. **Admin:** as rotas `/admin` e o controle de `is_admin` ficam fora da build de jogador. Se necessário para balanceamento durante DEV, habilitar somente pela configuração de desenvolvimento.
9. **Atividade/idle:** `GuildActivity.is_online`, heartbeat web e expiração da sessão de 5h/1h não definem mais a produção idle. Substituir por ciclo de vida da campanha/aplicativo e política de tempo da seção 6.
10. **Dados existentes:** a instalação não deve conectar ao PostgreSQL para funcionar. Importar automaticamente contas ou guildas atuais não é requisito desta entrega. A migração de código/conteúdo é obrigatória; importar uma guilda antiga do banco PostgreSQL fica opcional e separado, pois exigiria acesso explícito ao banco e mapeamento/validação de dados legados.

### 5.3 Pontos que exigem auditoria linha a linha durante DEV

Antes de declarar SQLite compatível, buscar e cobrir testes para:

- SQL textual/dialeto específico, locks, índices parciais, sequences e defaults;
- concorrência entre requests do servidor local e tarefas de timer;
- constraints, cascades e relações entre todas as tabelas de guilda;
- tipos de data/hora com e sem timezone;
- transações em recrutamento, upgrades, missões, loot, mercado, crafting, refino, desmontagem e conquistas;
- commits explícitos dentro de services e fluxos que assumem sessão de usuário;
- seeds/refinamentos de conteúdo repetidos no startup;
- referências a `current_user`, `request.session`, `user_id` e `is_admin` em todas as rotas/templates.

## 6. Tempo, progresso idle e alteração do relógio

### 6.1 Regra de gameplay

- A campanha não gera recompensa idle passiva enquanto o jogo estiver aberto.
- Ao encerrar o jogo, registrar o instante de saída de forma persistente.
- Ao reabrir a campanha, calcular o tempo offline, aplicar mínimo e teto configurados e conceder a recompensa uma única vez, em transação.
- Manter o teto atual de 8 horas como valor inicial de compatibilidade, configurável centralmente; qualquer mudança de balanceamento deve ser intencional e coberta por testes.
- Timers de missão, masmorra, chefe, taverna, mercado, crafting e desmontagem devem seguir uma política consistente e usar UTC persistido, sem gerar loot automaticamente antes da ação de coleta onde a regra atual exige coleta manual.

### 6.2 Limite técnico honesto

Num jogo 100% local, sem servidor ou fonte de tempo confiável externa, não existe forma perfeita de provar quanto tempo realmente passou enquanto o PC estava desligado. O relógio de parede do sistema pode ser alterado pelo próprio usuário. O jogo deve mitigar abuso e proteger contra bugs acidentais, mas não prometer anti-cheat absoluto para campanha individual.

### 6.3 Mitigação recomendada para a versão Windows

Implementar interface testável `ClockGuard`, sem espalhar lógica de relógio pelos serviços:

- Enquanto o aplicativo está aberto, medir duração de sessão com relógio monotônico do sistema; relógio monotônico não muda quando o usuário ajusta a hora.
- Para períodos que atravessam fechamento/reinicialização, persistir timestamps UTC e o maior horário confiável observado (high-water mark) por campanha.
- Guardar a âncora/high-water mark fora do arquivo de save, em armazenamento local protegido pelo usuário do Windows, e vincular ao identificador da campanha. A implementação pode usar proteção do sistema operacional, por exemplo DPAPI, atrás de uma interface isolada.
- Validar `now >= last_trusted_utc`; se voltar no tempo, conceder zero idle, manter a âncora futura, registrar anomalia e informar claramente o jogador. Não avançar a âncora para trás.
- Limitar recompensa por retorno a no máximo o teto offline e impedir crédito duplicado por replay do mesmo intervalo. Confirmar o crédito e o novo checkpoint na mesma transação.
- Se houver salto futuro incompatível com o último checkpoint, limitar o crédito ao teto, registrar a anomalia e avançar a âncora. Ao voltar o relógio, não gerar novo intervalo até alcançar a âncora.
- Se a âncora estiver ausente/corrompida, não conceder período retroativo automaticamente. Exibir recuperação/novo marco de tempo em vez de conceder várias horas.
- Ao importar um save em outro PC ou perfil Windows sem âncora protegida correspondente, iniciar uma nova âncora no momento da importação; não creditar tempo anterior à importação.
- Incluir controles DEV para injetar relógio falso nos testes; não depender de alterar o relógio real da máquina para QA.

Isso reduz exploração de rollback e concessões duplicadas. Um jogador determinado ainda pode manipular um jogo offline, alterar arquivos, apagar campanha ou avançar gradualmente o relógio. Evitar esse tipo de fraude de forma forte exigiria servidor autoritativo, que está fora do escopo desta versão.

### 6.4 Matriz de testes do relógio

- Saída limpa por 30 minutos: recompensa exata conforme fórmula e mínimo configurado.
- Saída por menos do mínimo: sem recompensa.
- Ausência acima do teto: recompensa limitada ao teto.
- Abrir a mesma campanha duas vezes sem nova ausência: não duplicar recompensa.
- Trocar horário para trás: zero recompensa, aviso e âncora preservada.
- Avançar o horário além do teto e depois retornar ao horário anterior: no máximo um teto concedido; depois, bloqueio até alcançar o high-water mark.
- Save reaberto após crash ou âncora inválida: recuperação segura, sem crédito duplicado nem perda automática do arquivo.
- Relógio monotônico durante a aplicação não deve ser afetado por ajuste de hora do Windows.

## 7. Entrada, UX e comportamento desktop

- Ao iniciar, abrir uma tela própria de campanhas: Continuar, Nova campanha e gerenciar saves.
- Nova campanha solicita nome da guilda e aplica o fluxo inicial atual, sem conta/login.
- Janela redimensionável, lembrar posição/tamanho se confiável e ter ícone/nome do aplicativo.
- Fechar janela deve executar encerramento limpo, persistir estado e finalizar servidor local. Oferecer confirmação se houver operação pendente ou falha de save.
- Links externos não podem navegar dentro da janela do jogo sem controle; abrir navegador externo apenas para links explicitamente permitidos.
- Preservar UX medieval/fantasia e responsividade; a janela própria não significa abandonar HTML/Jinja.
- Erros de banco, migration, backup ou conteúdo devem aparecer como telas de recuperação compreensíveis em PT-BR, com logs técnicos separados.
- Não depender de conexão, telemetria, GitHub, CDN ou fontes remotas para inicializar, jogar, renderizar ícones ou obter recompensas.

### 7.1 Identidade visual e sprites

A nova identidade deve ser implementada no aplicativo, não permanecer apenas em mockups. A DA deve produzir sprites bitmap originais e locais para toda categoria visual usada no jogo: navegação e ações, classes e evoluções, representação de mercenários, tipos de equipamentos e slots, materiais e recursos, construções, operações e demais sistemas. Um sprite canônico pode representar um grupo semântico de itens gerados; não é necessário desenhar cada instância procedural, mas nenhum grupo pode depender de um símbolo genérico por falta de cobertura.

Um manifesto versionado associa códigos e grupos de domínio aos arquivos e define fallback acessível. Raridade, seleção, bloqueio e estado continuam expressos também por texto/estrutura, não apenas por cor ou imagem. Os sprites devem permanecer legíveis nos tamanhos reais da interface, ter masters e exportações otimizadas e estar disponíveis offline. A distribuição não deve depender de ícones legados cuja procedência de uso e redistribuição não foi confirmada.

## 8. Desenvolvimento sem reinstalar a cada mudança

### 8.1 Decisão

Durante DEV, executar diretamente a cópia do projeto e abrir a mesma aplicação em pywebview. Não criar updater que faça `git pull` no PC do usuário e não reinstalar o aplicativo a cada alteração de código.

Fluxo de desenvolvimento esperado:

```powershell
cd "C:\Users\vitor\Guild Idle Manager\App GIM"
& 'C:\Users\vitor\Guild Idle Manager\.venv\Scripts\python.exe' -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-desktop-dev.txt
.\.venv-desktop\Scripts\python.exe -m app.desktop
```

O agente deve criar `requirements-desktop-dev.txt` (ou equivalente) para incluir dependências desktop/dev sem forçar instalação de PostgreSQL. Criar `Iniciando_jogo_dev.bat` para ativar o ambiente existente e iniciar a janela. O script deve **não** executar `pip install` nem migration Postgres a cada abertura.

Mudanças em Python: reiniciar o processo desktop para carregar código atualizado. Mudanças em Jinja/CSS/JS: oferecer reload de janela em DEV (atalho documentado, por exemplo Ctrl+R) e cache desabilitado. A solução não deve alterar ou apagar o save durante reload.

O `Iniciando_venv.bat` atual continuará pertencendo ao fluxo web/PostgreSQL até ser explicitamente substituído; nomear separadamente os dois modos para evitar que o jogador dependa de banco local externo.

### 8.2 Atualização de uma build distribuída

O updater via GitHub não faz parte do primeiro DEV. Para um release futuro, a abordagem segura é publicar releases versionadas/assinadas, buscar um manifesto de release, validar assinatura/hash, baixar para staging, fechar o app, fazer backup dos saves, aplicar atualização/migrations e oferecer rollback. Nunca executar script arbitrário recebido de branch ou baixar código sem validação. Isso deve ser uma entrega própria, depois de existir canal de release e assinatura.

## 9. Plataforma e empacotamento

### Fase inicial

- Windows 10/11 x64, build de desenvolvimento a partir do checkout e instalador DEV para validação.
- Empacotar o runtime com PyInstaller, templates, static assets, dados JSON e migrations.
- Gerar instalador Windows que preserve `%LOCALAPPDATA%\GuildIdleManager` ao atualizar/desinstalar, salvo pedido explícito de apagar saves.
- Testar numa máquina sem Python e sem PostgreSQL instalados.

### Expansão futura

macOS e Linux devem ter builds nativos separados, com verificação específica de WebView, dependências, caminhos de save e assinatura. A documentação do pywebview lista Windows, macOS e Linux, mas dependências nativas variam por sistema. [Instalação do pywebview](https://pywebview.idepy.com/en/guide/installation)

Steam, auto-update e versão online não são requisitos da DEV offline.

## 10. Escopo fora desta entrega

- Login, cadastro, conta remota, sincronização de save e multiplayer.
- Servidor central, PostgreSQL em produção e competição online.
- Anti-cheat inviolável ou relógio confiável sem rede.
- Atualizador automático via GitHub.
- Port para celular, macOS ou Linux na primeira build.
- Refazer a interface como SPA, React, Vue ou Angular.
- Rebalanceamento geral de conteúdo que não seja requisito de compatibilidade.
- Migração automática do banco PostgreSQL local atual para campanhas desktop. Se desejado, criar depois importador explícito, com backup e relatório de validação.

## 11. Plano de implementação em até três trabalhos

### Trabalho 1 — Core offline e persistência

- Criar modo/configuração desktop e caminho de campanha SQLite.
- Refatorar criação de engine/session para campanha selecionada.
- Resolver dependência `user -> guild`, remover autenticação/middleware da entrada desktop e manter rotas de gameplay.
- Criar campaign metadata, criar/abrir campanha e aplicar conteúdo inicial versionado uma única vez.
- Tornar queries, locks, constraints e migrations necessárias compatíveis com SQLite.
- Preservar seed de conteúdo e valores de gameplay atuais sem reexecutar balance patches cegamente.

### Trabalho 2 — Janela desktop, ciclo de vida e saves

- Criar launcher pywebview + FastAPI local em loopback, healthcheck, tratamento de encerramento e janela de campanhas.
- Implementar backup/export/import, migração/restauração de saves e diretórios de usuário, incluindo rollback automático validado quando uma migration falhar.
- Implementar `ClockGuard`, regra idle, recuperação após crash e matriz de relógio da seção 6.
- Ajustar base route/menu e telas essenciais para fluxo sem login.
- Criar launcher DEV que executa do código-fonte sem reinstalação e sem PostgreSQL.

### Trabalho 3 — Empacotamento, regressão e build DEV

- Empacotar PyInstaller e instalador DEV Windows.
- Validar startup offline numa máquina/ambiente limpo sem Python/PostgreSQL.
- Rodar testes atuais e novos, corrigir incompatibilidades encontradas e testar fluxo de todos os sistemas preservados.
- Documentar instalação, execução DEV, saves/backups, recovery, limitações do relógio e atualização futura.
- Produzir artefato instalável DEV e relatório de QA com evidências.

Trabalhos 1 e 2 podem ser combinados se o agente conseguir manter os testes claros. Trabalho 3 é gate obrigatório antes de chamar a build de testável.

## 12. Comandos e diretrizes DEV

### Uma vez por checkout

```powershell
cd "C:\Users\vitor\Guild Idle Manager\App GIM"
& 'C:\Users\vitor\Guild Idle Manager\.venv\Scripts\python.exe' -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-desktop-dev.txt
```

### Rodar direto do código

```powershell
.\.venv-desktop\Scripts\python.exe -m app.desktop
```

### Testes

```powershell
.\.venv-desktop\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-desktop\Scripts\python.exe scripts\balance\validate_content.py
.\.venv-desktop\Scripts\python.exe scripts\prd_qa.py
.\.venv-desktop\Scripts\python.exe scripts\prd2_progression_qa.py
.\.venv-desktop\Scripts\python.exe scripts\prd3_dungeons_bosses_qa.py
```

O agente deve conferir os nomes reais dos scripts antes de copiar comandos para README/CI. QA que atualmente exige PostgreSQL deverá receber modo SQLite ou fixture isolada; testes de gameplay não podem depender de dados da guilda real do usuário.

### Build de desenvolvimento

```powershell
.\.venv-desktop\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\GuildIdleManager.spec
```

O caminho/spec final fica a cargo da implementação e deve ser documentado. O instalador só é aceitável após testar em ambiente limpo; durante desenvolvimento diário, rodar diretamente da pasta do código.

## 13. Critérios de aceite

### Inicialização e offline

- Aplicativo inicia numa janela própria, sem abrir navegador, console ou pedir URL.
- Funciona sem internet e sem PostgreSQL instalado/rodando.
- Nenhum login, cadastro ou conta é solicitado.
- Criar duas campanhas isoladas, sair e retomar cada uma sem cruzar estado.
- Fechar e reabrir não perde dados; ação não confirmada não aparece como concluída.

### Gameplay e conteúdo

- Validar pelo menos um fluxo end-to-end de mercenário, missão, loot, item/equipamento, construção, masmorra/chefe, mercado, doca, profissão, ferreiro, progresso, conquista e Codex.
- Conferir timers e coleta manual; o backend local continua sendo fonte de verdade.
- Conteúdo está disponível sem rede; startup não altera silenciosamente configuração/progresso a cada abertura.
- UI permanece PT-BR, com assets locais carregados.

### Saves e atualização

- Backup, exportação e importação passam por validação de formato e integridade.
- Save de versão anterior é migrado com backup e mensagem; falha permite restaurar.
- Atualizar/reinstalar o aplicativo não remove saves.
- Executar pelo checkout DEV reflete as alterações sem reinstalar o app.

### Relógio e idle

- Idle só é calculado para intervalo fechado/offline, nunca enquanto a janela está ativa.
- Mínimo, teto, arredondamento, transação única e duplicidade cobertos por testes.
- Casos de rollback e salto de relógio exibem comportamento definido na seção 6.
- Documentação deixa claro que proteção local é mitigação, não garantia inviolável.

### Qualidade

- Suite automatizada web existente continua passando ou é adaptada com justificativa.
- Testes SQLite para todos os fluxos transacionais críticos.
- Smoke test em pasta limpa, sem `.env`, sem PostgreSQL e sem conexão.
- Nenhum segredo, `.env` real, nome de usuário ou senha de teste incluído na build.
- O relatório identifica testes não executados e incompatibilidades remanescentes.

## 14. Riscos e decisões explícitas

1. **Compatibilidade Postgres/SQLite:** há lock e SQL específicos; não basta trocar `DATABASE_URL`. Criar compatibilidade real antes do empacotamento.
2. **Seeds de startup:** aplicar seeds e balance passes toda abertura pode ressuscitar ou sobrescrever conteúdo. Passar a conteúdo versionado por campanha.
3. **Remoção de login:** muitos endpoints/templates derivam contexto de `current_user`. Criar contexto de campanha consistente em todas as rotas.
4. **Timer/idle local:** não há relógio confiável durante desligamento sem servidor. Limites e high-water mark reduzem o abuso, mas não eliminam adulteração intencional.
5. **Dados existentes:** a campanha desktop começa local e não depende das contas/guildas PostgreSQL atuais. Importação da guilda existente deve ser um fluxo explícito e opcional, não uma conexão escondida.
6. **Build desktop:** pywebview depende do runtime WebView apropriado; validar num Windows limpo e tratar instruções/instalação do WebView2 se necessário.
7. **Sem Git identificado:** nesta revisão a pasta raiz não apresentou metadados `.git`. O GDD não pressupõe commits, branches ou CI existentes. Recomenda-se colocar o projeto sob controle de versão antes de uma grande refatoração, preservando o estado atual como baseline.

## 15. Orientação final ao agente DEV

Implementar este documento como uma evolução do jogo existente, não como um protótipo paralelo. Primeiro verificar a árvore e o estado real; não apagar rotas, dados, assets, testes ou ferramentas de QA sem substituição. Fazer mudanças pequenas por camada, manter o modo web atual executável durante a transição quando possível e não usar banco ou guilda real em testes automatizados.

Antes de declarar pronto, entregar: lista de módulos reaproveitados/alterados, estratégia de migrations SQLite, comandos reais de DEV/build, resultado dos testes, evidência de inicialização sem internet/PostgreSQL, localização do save, resultado dos testes de relógio e limitações conhecidas.
