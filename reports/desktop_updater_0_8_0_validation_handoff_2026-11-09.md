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

## Caminho distribuível pelo GitHub Actions

### Evidência do runner Windows

- O run [15 — DEV-v0.7.1](https://github.com/Vitor41/guild_idle_manager/actions/runs/42627198698), no commit `17a080385e6892b1b84c35250e48bb5299a0041f`, terminou com sucesso em 9 nov 2026. Os logs identificam Windows Server 2025 e registram a criação de `GuildIdleManager-DEV.zip` e `GuildIdleManager-DEV-Setup.exe`, execução do smoke, geração do manifesto assinado e publicação. Isso comprova que o caminho de empacotamento/IExpress funciona no runner hospedado para aquele commit e ambiente.
- O run é anterior ao candidato 0.8.0 e não o valida. A API retornou zero artifacts retidos; os binários foram publicados como release assets.

### Gates locais e de CI

| Gate | Limitação observada no host local | Gate apropriado no Windows Actions |
|---|---|---|
| Runtime para build | `.venv-desktop` resolve para o Python do Codex; `_ssl`/`_tkinter` falham no carregamento de DLL e o `ssl.py` contém uma dependência local que o verificador rejeita. O CPython embeddable 3.12.10 usado na tentativa seguinte não traz Tk nem PyInstaller; o hook do PyInstaller marcou tkinter como quebrado. | Usar o Python completo instalado no runner (`py -3.12`, como no workflow) com `requirements-desktop-dev.txt`; manter a validação de SSL e exigir que PyInstaller inclua Tk/Tcl antes de aceitar o build. |
| TEMP e SQLite | O Python não consegue criar temporários fora das raízes graváveis e recua para o diretório do repositório. Isso invalida testes que exigem chave privada fora do repo e reproduz o erro do SQLite durante a inserção em lote. | Apontar `TEMP`, `TMP`, `LOCALAPPDATA`, `APPDATA` e `GIM_SMOKE_TEMP_DIR` para subpastas explícitas de `RUNNER_TEMP`; verificar marcador PASS, DB de campanha e seleção de campanhas. |
| IExpress | A chamada local terminou com código 1 e não criou o wrapper Setup; o instalador foi validado diretamente pelo script PowerShell. | Executar o script de build completo no runner, exigir Setup presente e tamanho estável e validar seu hash antes da assinatura. O run 15 demonstra essa etapa para 0.7.1. |
| Instalação e preservação de save | A instalação do script funcionou elevada somente no perfil descartável. As restrições de leitura do runtime Tk no caminho temporário tornaram a tentativa sem elevação inconclusiva. | Instalar o Setup em perfil isolado sob `RUNNER_TEMP`, usando `GIM_SETUP_RESULT` e `GIM_SETUP_EXPECTED_LOCALAPPDATA`; comparar o hash de um save-fixture antes/depois e confirmar o marcador da versão. O workflow atual ainda não instala o Setup. |
| Revisão visual | O CI não comprova o comportamento interativo de mouse, teclado, toque, zoom e larguras solicitadas. | Manter inspeção visual manual como gate separado; não usar smoke CLI como substituto. |

### Fluxo seguro recomendado

1. Adicionar um workflow ou modo `build-only` de `workflow_dispatch` que receba um ref imutável, construa no runner Windows, execute os smokes e instale o Setup em perfil temporário. Ele deve publicar o ZIP e Setup como artifact com retenção curta, sem criar GitHub Release nem usar segredo de assinatura.
2. Depois do aceite CR, da revisão visual e do teste de save isolado, o fluxo de release pode assinar o Setup e publicar o manifesto apenas no ambiente protegido. O workflow atual faz build, assinatura e `gh release create` no mesmo job; portanto, dispará-lo agora não é um modo seguro de obter apenas um candidato.
3. O job de build-only deve fixar o commit SHA recebido, registrar versão, Windows runner image, Python completo, versões resolvidas das dependências, SHA-256 de ZIP/Setup e logs/marcadores dos smokes. `windows-latest` e a dependência `cryptography>=42,<50` não garantem build byte a byte idêntico; use imagem/versionamento e lock com hashes se essa propriedade for exigida.
4. A aprovação de ambiente `release-signing` e as proteções do branch principal não foram inspecionadas. Não conte com elas como gate CR até confirmar configuração e responsáveis diretamente no GitHub.

O workflow de release seleciona tags `DEV-vMAJOR.MINOR.PATCH` apenas quando apontam para commit integrado no branch padrão, confere `APP_VERSION`, valida chave pública/segredo, constrói, executa smoke, assina e publica. Esse encadeamento é útil para release aprovada, mas não permite obter um artifact de 0.8.0 sem publicar. Nenhum workflow foi disparado nesta investigação.

Na alteração candidata posterior, a etapa de smoke do workflow foi alinhada ao build: usa um diretório aleatório em `RUNNER_TEMP`, aponta `LOCALAPPDATA`, `APPDATA`, `GIM_SMOKE_TEMP_DIR`, `TEMP` e `TMP` para dados isolados e exige PASS da seleção de campanhas e da janela launcher, com timeouts de 120s/30s. Dois testes de contrato do workflow passaram. O workflow continua sem teste de instalação do wrapper Setup e ainda publica automaticamente; a opção segura para coletar um artifact antes do release requer um workflow/mode build-only separado.
