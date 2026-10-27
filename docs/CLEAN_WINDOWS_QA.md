# Validação externa do instalador desktop DEV

Este roteiro fecha a pendência do GDD §9/§13 que não pode ser comprovada no computador de desenvolvimento. Execute-o em outro Windows 10/11 x64 sem Python nem PostgreSQL. Não use uma campanha importante; crie uma campanha descartável. Registre versão do Windows, hash SHA-256 do Setup, resultado e qualquer erro/captura em `WORK3_QA_DESKTOP.md` antes de aceitar o GDD.

## Preparação

1. Transfira somente `dist/GuildIdleManager-DEV-Setup.exe` da build final. Confira o SHA-256 contra o valor do relatório de QA antes de executar. Não instale Python, PostgreSQL, Git ou dependências do projeto para este teste.
2. Desconecte a rede do computador de teste antes de iniciar a instalação e mantenha-a desligada até completar o primeiro ciclo de jogo. Não desative antivírus nem proteções do Windows para forçar a instalação; registre qualquer bloqueio.
3. Anote se já existe `%LOCALAPPDATA%\GuildIdleManager` ou `%LOCALAPPDATA%\Programs\GuildIdleManager`. Se existir, não apague: use outro perfil Windows limpo ou interrompa este teste para não misturar dados.

## Primeiro ciclo

1. Execute o Setup e abra o atalho `Guild Idle Manager DEV`. O aplicativo deve abrir em janela própria, sem console, navegador, URL, pedido de login, conexão ou instalação de banco. Registre se o smoke do instalador falhar.
2. Crie uma campanha de teste e uma guilda; anote os nomes. Verifique que a tela inicial, menu, sprites, construção, Taverna, Mercenários, Missões e Masmorras carregam com imagens locais.
3. Construa o primeiro Alojamento/Taverna conforme os recursos iniciais, contrate um Aprendiz e inicie uma missão curta. Antes do fim, o backend deve recusar coleta; após o timer, colete manualmente e confira o resultado.
4. Feche a janela pelo controle normal. Verifique no Gerenciador de Tarefas que o processo e o servidor local encerraram. Reabra pelo atalho e continue a mesma campanha: mercenário, construção e missão devem persistir. O progresso idle deve aparecer apenas pelo período fechado, sem duplicar ao reabrir novamente logo em seguida.
5. Abra uma segunda campanha descartável e confira que os dados da primeira não aparecem nela. Retorne à primeira e confirme a persistência.

## Atualização sem perda

1. Guarde uma cópia do Setup e do hash usados no primeiro ciclo. Quando houver uma build posterior, execute o novo Setup com o aplicativo fechado. Não remova o diretório de saves.
2. Abra as duas campanhas e confira os dados anteriores. Se houver migração de save, deve aparecer aviso de atualização e backup. Uma segunda abertura não deve repetir o aviso nem reaplicar recompensas.
3. Registre o caminho do backup e a versão do pacote no relatório, sem anexar saves pessoais ou dados sensíveis ao Git.

**Aceite:** todos os passos acima passam sem Python, PostgreSQL e rede. Falha de instalação, janela em branco, perda de save, timer incorreto ou dependência online reabre o gate; não aprovar o GDD apenas pelo smoke feito no computador de desenvolvimento.
