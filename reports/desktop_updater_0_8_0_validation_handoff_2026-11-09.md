# Validação do updater desktop 0.8.0 — handoff

## Estado

**Candidato apto para revisão CR; release continua fechado.** O smoke empacotado confirmou a abertura do launcher e a rota de seleção de campanhas. O script do Setup corrigido também concluiu a instalação no perfil temporário e preservou o save. Não houve inspeção visual manual nem criação/publicação de um novo Setup IExpress nesta rodada.

## Evidência

- `tests.test_launcher_update_flow` e `tests.test_launcher_ui_contracts`: 10 testes passaram.
- Smoke offline do executável empacotado: `PASS: SQLite, campanhas temporárias, seleção de campanhas, nomes e manifesto local`.
- Smoke do launcher empacotado: `PASS: packaged launcher entry; window initialized, current-version state and open-game action rendered`.
- Executável candidato: 12.849.610 bytes, SHA-256 `5531E99AB7C3481654363C9D01C2F6E1683F4EB6BB369751975D78DCA32579C4`. A cópia usada no pacote com o script atualizado tem o mesmo hash. As alterações posteriores ao build validado foram no script do Setup; nenhum arquivo Python do aplicativo mudou.
- ZIP temporário com o Setup corrigido: 74.566.800 bytes, SHA-256 `74B1900A4DAAECD9F202748FCEE9FA771D3F2977335D971E5081B7D56902014D`.
- `Install-Desktop-Dev.ps1` foi executado diretamente, com elevação, apenas em `%TEMP%\GIM-Updater-E2E-mw1d4lce\profile-handoff-regression`. O marcador final indica canal DEV, versão 0.8.0 e produto `org.guildidlemanager.desktop`.
- Save `860858a7-e9bc-49e3-b3f3-8e7e2e698408.db`: 5.439.488 bytes; SHA-256 antes e depois `0D23110C11C19027D9436F163C686C669F585CEAFEEC80296B5E8BE73AAC0C03`.
- A falha anterior do Setup foi causada por atribuir a saída vazia de `Assert-NoReparsePoint` a `$smokeProfile`. O script agora apenas executa a validação e preserva o caminho.
- Um novo build com o runtime embeddable sem Tk não é evidência válida: PyInstaller avisou que excluiria tkinter e o smoke não gerou marcador. O EXE acima vem do build anterior, cujo smoke passou; a cópia e o hash foram conferidos antes do teste do Setup.

## Limites e próximos gates

- A criação do wrapper IExpress falhou com código 1 neste ambiente; o teste cobriu o script de instalação diretamente e o ZIP atualizado, não um novo `Setup.exe` autônomo.
- A execução combinada de 24 testes também encontrou falhas nos testes de assinatura e no smoke HTTP porque `tempfile` caiu no diretório do repositório e o SQLite não conseguiu abrir o banco durante a carga de modelos. Esses resultados não foram tratados como aprovados. A bateria limpa de 10 testes de launcher passou.
- Não houve inspeção visual nas larguras 1440, 1024, 760 e 420 px, zoom 200%, nem verificação manual de mouse, teclado e toque. Os critérios ML-031–034 e BUG-009 ainda exigem gate visual.
- Não se deve publicar ou liberar o Setup/release até produzir um wrapper final rastreável, repetir os smokes sobre esse artefato e fechar a revisão CR e a inspeção visual.
- O perfil normal e seus saves não foram usados. O processo normal que já estava aberto permaneceu intocado.
