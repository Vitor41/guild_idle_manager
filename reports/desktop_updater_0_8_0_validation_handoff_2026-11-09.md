# Validação do updater desktop 0.8.0 — handoff

## Estado

**Não aprovado para aceite visual/E2E ou release.** O commit `0e0dcd0e16ebffae6580bb95e10f0d38dfc60ba1` contém a implementação e os testes focados, mas ainda não há evidência de uma atualização instalada de ponta a ponta em perfil temporário.

## Evidência disponível

- Testes Python focados: 21 passaram, cobrindo fluxo do launcher, contratos de interface, Guia e duração de venda.
- Testes frontend: 6 passaram, cobrindo exportação do Guia e detalhes de equipamento.
- `compileall` e `git diff --check` passaram.
- O smoke HTTP (`tests.test_desktop_http_smoke`) não iniciou: FastAPI exige `python-multipart`, ausente em `.venv-desktop`. A dependência consta em `requirements-desktop-dev.txt` (linha 27), mas não foi localizado wheel na instalação nem no cache local.
- Há um processo `GuildIdleManager.exe` cujo caminho aponta para `%LOCALAPPDATA%\Programs\GuildIdleManager`, a instalação normal. Ele não foi encerrado nem usado para testes. Nenhuma nova instalação foi iniciada.
- As capturas anteriores registram falha ao abrir o Setup validado por bloqueio de arquivo em uso (`WinError 32`); portanto, não comprovam atualização concluída nem preservação do save após instalação.

## Plano para fechar o gate

1. Preparar um ambiente descartável de build/teste a partir de `requirements-desktop-dev.txt`, usando um wheel já disponível ou o ambiente isolado de CI; não alterar o ambiente global nem instalar dependências na instalação do jogo.
2. Executar o smoke HTTP e os testes de launcher após a dependência estar disponível.
3. Criar ou restaurar um perfil descartável sob `%TEMP%` e confirmar que seu `LOCALAPPDATA` aponta exclusivamente para esse diretório. Registrar a versão inicial e o hash dos arquivos de save de teste.
4. Construir o Setup candidato deste branch e executar o instalador somente com o perfil descartável selecionado. Não fechar processo cujo caminho não pertença claramente a esse perfil.
5. Confirmar que o instalador termina, a versão exibida é 0.8.0, o launcher chega à seleção de campanhas, os saves mantêm os mesmos hashes e os logs registram o handoff sem erro.
6. Fazer a inspeção visual nas larguras 1440, 1024, 760 e 420 px, zoom 200%, mouse, teclado e toque; registrar capturas e resultados para cada critério ML-031–034 e BUG-009.
7. Encaminhar o commit e as evidências à revisão CR. Manter o gate de release fechado até E2E, inspeção visual e CR aprovados.

## Limites

Este relatório não altera nem aprova os critérios. Testes unitários e de contrato não substituem a instalação temporária, a comparação do save, a inspeção visual ou a revisão CR. Perfil real, release publicada e instalação no perfil normal permanecem fora deste teste.
