# Atualização do aplicativo

Versão local atual: `0.3.0` (`app/core/version.py`, também publicada como `FastAPI.version`), incremento menor da rodada de melhorias de outubro de 2026. Incrementos seguintes de funcionalidade usam `0.1` na versão menor; a versão major fica reservada a mudança arquitetural/de design relevante ou lançamento de plataforma.

## DEV a partir do checkout

A tela `/updates` oferece **Verificar versão do checkout**. O endpoint lê `APP_VERSION` dos arquivos já presentes no checkout, sem importar ou executar o arquivo. Quando a versão em disco for superior à carregada, **Reiniciar e aplicar versão do projeto** solicita o fechamento da janela; o launcher encerra o servidor e executa o hook normal de shutdown/saves, libera o mutex e inicia novamente `sys.executable -m app.desktop` a partir da raiz deste checkout. Assim o processo recarrega os arquivos Python, templates, CSS e JavaScript já existentes no disco. Essa ação não busca código, não executa `git pull`, não baixa nem substitui arquivos. Não há origem Git remota configurada neste checkout. O botão não aparece no modo frozen.

## Atualizar uma cópia instalada

Pacotes `sys.frozen` podem consultar o GitHub Releases depois que owner, repo, canal e chave pública Ed25519 estiverem configurados e corresponderem ao marcador de instalação. A consulta só ocorre ao pressionar o botão; o módulo valida a release/tag e semântica prerelease do canal, a assinatura dos bytes do manifesto, o produto/schema/SemVer/mínimo e o SHA-256 do Setup antes de habilitar a instalação. O Setup é baixado para uma pasta temporária dedicada, revalidado pelo hash ao solicitar a instalação e só é aberto após confirmação explícita; o launcher fecha o app e aguarda seu processo terminar antes de abrir o instalador.

O instalador recebe o canal (`DEV`, `beta` ou `stable`) do pacote, exige que um destino existente tenha o mesmo marcador de produto/canal, executa seu smoke offline na cópia staged e troca os arquivos com backup/rollback. Os saves permanecem em `%LOCALAPPDATA%\GuildIdleManager\saves`. O build pode selecionar o canal com `scripts/build_desktop_dev.ps1 -Channel stable` ou `-Channel beta`; o default preserva DEV. Nenhum build, Setup ou instalação foi executado nesta entrega.

## Situação

**Decisão confirmada: GitHub Releases.** O cliente e o Setup por canal estão implementados, mas owner/repo/chave permanecem sem valores padrão. Sem configuração completa e marcador correspondente, a tela desabilita a consulta e nenhum pedido de rede é feito. O checkout continua sem remote Git configurado, e a conta GitHub conectada não tem acesso ao repositório Guild Idle Manager; por isso não foi possível configurar uma origem real, publicar nem validar uma release. Até uma release assinada ser publicada no repositório configurado, a instalação permanece indisponível com mensagem de estado.

## Contrato GitHub Releases v1

- Configuração por ambiente: `GIM_GITHUB_RELEASES_OWNER`, `GIM_GITHUB_RELEASES_REPO`, `GIM_GITHUB_RELEASES_CHANNEL` e `GIM_GITHUB_RELEASES_PUBLIC_KEY` (chave pública Ed25519 codificada em Base64, 32 bytes). `GIM_GITHUB_RELEASES_MANIFEST_ASSET` seleciona o asset JSON e, por padrão contratual, é `gim-release.json`.
- Canal `stable` usa releases estáveis; `beta` e `DEV` usam releases prerelease. A tag segue `<channel>-v<version>` (por exemplo, `stable-v1.2.3`, `beta-v1.2.3` ou `DEV-v1.2.3`). Owner, repositório, canal e chave não têm valores padrão; manifesto com nome inválido também bloqueia a configuração.
- Cada release contém o asset JSON do manifesto e o asset de assinatura destacado `<manifesto>.sig`. A assinatura Base64 Ed25519 cobre os bytes exatos do manifesto. O manifesto UTF-8 contém `schema_version` (inteiro `1`), `app_id` (`guild-idle-manager`), `version` (SemVer), `channel`, `minimum_supported_version`, `asset_name` (nome do instalador anexado à mesma release) e `asset_sha256` (64 caracteres hexadecimais minúsculos). Releases devem marcar prerelease de acordo com o canal.
- O cliente confere canal/tag, prerelease, schema, app id, SemVer, versão mínima, presença do asset, assinatura pela chave configurada e SHA-256 antes de oferecer um Setup. Falhas bloqueiam download ou instalação. `minimum_supported_version` marca atualizações obrigatórias na mensagem; toda atualização ainda exige confirmação explícita. `/updates/check` pode baixar apenas para staging temporário; `/updates/install-release` exige o estado verificado mantido no processo e recalcula o SHA-256 antes do handoff ao Setup.
- O Setup aplica os arquivos do app através de staging, smoke offline, backup temporário e rollback em falha; os saves ficam fora da árvore instalada. O handoff espera o encerramento do app antes de iniciar Setup. A configuração vazia mantém o fluxo fail-closed. Código e testes foram adicionados, porém nenhum teste, build, Setup, instalação, revisão QA ou inspeção visual foi executado nesta entrega.

## Requisitos para distribuição

Antes de distribuição, criar/configurar o repositório autorizado, gerar e proteger a chave privada fora do cliente, empacotar a chave pública, publicar Setup/manifesto/assinatura consistentes e conferir o pacote publicado. O produto não migra nem copia saves porque o Setup substitui somente a árvore de programa; qualquer migração futura precisa de backup próprio.
