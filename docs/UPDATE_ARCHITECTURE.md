# Atualização do aplicativo

Versão funcional desta entrega: `0.8.0` (`app/core/version.py`).

## Fluxo do launcher

No pacote desktop, o atalho abre `GuildIdleManager.exe` sem entrar em uma campanha. O launcher consulta o canal registrado na instalação, valida tag, metadados e assinatura Ed25519 do manifesto, e confere o SHA-256 do Setup antes de oferecer a atualização. O Setup só é baixado para staging temporário após a validação do manifesto; seu hash é conferido durante o download e novamente antes da abertura.

O launcher mostra progresso e oferece **Atualizar e jogar**. Para atualizações opcionais, também permite **Jogar versão instalada** ou **Adiar**, inclusive quando a rede falha. Quando `minimum_supported_version` torna a atualização obrigatória, a versão antiga não pode iniciar. O instalador abre em janela visível, e o fluxo só segue para a seleção de campanhas depois que o Setup confirma a versão instalada. Nenhum aviso do Windows é ocultado ou contornado.

Um mutex nomeado por perfil impede múltiplos launchers. Durante a atualização, um bloqueio exclusivo em `%LOCALAPPDATA%\GuildIdleManager\locks\update-handoff.lock` e a posse do mutex serializam o Setup. Isso evita que uma segunda tentativa abra o mesmo perfil enquanto a primeira ainda está atualizando.

Os saves ficam fora dos arquivos do programa, em `%LOCALAPPDATA%\GuildIdleManager\saves`. O Setup substitui somente a pasta de instalação gerenciada e mantém o mecanismo existente de staging, backup e rollback. Após confirmar a nova versão, o helper libera o bloqueio e abre o executável instalado na seleção de campanhas. O atalho continua apontando para o executável que o Setup atualiza.

## Atualizações durante uma campanha

A tela `/updates` permite somente **Verificar atualizações**. Ela informa a versão disponível e orienta a fechar a campanha e abrir o launcher pelo atalho. O endpoint não baixa nem instala arquivos. Para um checkout local DEV, a página também é apenas informativa; novas alterações locais passam a valer ao reiniciar o aplicativo.

## Diagnóstico

- `%LOCALAPPDATA%\GuildIdleManager\logs\desktop.log`: inicialização e erros gerais.
- `%LOCALAPPDATA%\GuildIdleManager\logs\update-launcher.log`: diagnóstico do launcher de atualização.
- `%LOCALAPPDATA%\GuildIdleManager\logs\update-handoff.log`: helper, Setup, streams capturados e confirmação/erro do handoff.
- Uma falha depois da validação, durante o handoff ou a execução do Setup, preserva o instalador no staging temporário para tentativa manual; downloads parciais ou inválidos são removidos. O diálogo informa o caminho e o log.

## Confiança e canal

Owner, repositório, canal e chave pública vêm da configuração da distribuição e do marcador da instalação. A chave privada de assinatura é exclusiva do ambiente de publicação e não deve ser incluída no repositório, no pacote nem em logs. `DEV`, `beta` e `stable` só aceitam releases do próprio canal. Sem chave pública válida ou com assinatura, metadados ou hash inválidos, o launcher não oferece a execução do Setup.

## Limites da validação desta entrega

Os testes automatizados usam assinaturas e dados temporários. Eles não substituem uma revisão independente do commit nem a aceitação manual da interface e de uma atualização instalada em perfil temporário. Nenhum perfil ou save real deve ser usado para essa validação.
