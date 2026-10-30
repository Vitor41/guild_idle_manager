# Atualização do aplicativo

Versão local atual: `0.2.0` (`app/core/version.py`, também publicada como `FastAPI.version`), primeiro incremento menor desde `0.1.0`. Incrementos seguintes de funcionalidade usam `0.1` na versão menor; a versão major fica reservada a mudança arquitetural/de design relevante ou lançamento de plataforma.

## DEV a partir do checkout

A tela `/updates` oferece **Verificar versão do checkout**. O endpoint lê `APP_VERSION` dos arquivos já presentes no checkout, sem importar ou executar o arquivo. Quando a versão em disco for superior à carregada, **Reiniciar e aplicar versão do projeto** solicita o fechamento da janela; o launcher encerra o servidor e executa o hook normal de shutdown/saves, libera o mutex e inicia novamente `sys.executable -m app.desktop` a partir da raiz deste checkout. Assim o processo recarrega os arquivos Python, templates, CSS e JavaScript já existentes no disco. Essa ação não busca código, não executa `git pull`, não baixa nem substitui arquivos. Não há origem Git remota configurada neste checkout. O botão não aparece no modo frozen.

## Atualizar a cópia instalada DEV

Pacotes `sys.frozen` não têm feed nem atualizador: a aplicação mostra a versão empacotada e declara que não sabe se há versão mais recente; ela não oferece a ação de reinício do checkout. Para atualizar uma instalação DEV gerenciada, é necessário receber `GuildIdleManager-DEV-Setup.exe` por um canal confiável, fechar o jogo e executar o Setup sobre a instalação DEV existente. O script atual instala os arquivos em `%LOCALAPPDATA%\Programs\GuildIdleManager` e os saves permanecem separados em `%LOCALAPPDATA%\GuildIdleManager\saves`; o script não migra nem substitui essa pasta de dados. O Setup troca os arquivos do app com staging e backup temporário, mas só aceita a instalação que contém seu marcador DEV. Este fluxo manual não foi executado nesta entrega.

## Situação

O projeto não contém feed de lançamentos, manifest assinado, verificação de assinatura/checksum, pacote de produção nem serviço de instalação automática. A ação local reinicia o checkout já alterado no disco; ela não atualiza a fonte. **Decisão confirmada para produção: GitHub Releases.** O checkout continua sem remote Git configurado, e a conta GitHub conectada não tem acesso a um repositório Guild Idle Manager; portanto owner/repo e URL não foram confirmados e nenhuma consulta/remessa de release é ativada.

Sem owner/repo, a fundação segura oferece campos configuráveis sem credenciais padrão, valida os componentes e a chave e deixa consulta e instalação explicitamente desativadas. Mesmo com campos preenchidos, o código permanece fail-closed até existir leitor de releases, verificador de assinatura e aplicador transacional revisados. O módulo não faz chamadas de rede. Dependem do owner/repo confirmado e acesso ao repositório: configurar a origem real, publicar Setup/manifesto/assinatura, fixar a chave pública e validar o pacote publicado. O próximo passo mínimo é fornecer o owner/repo exato e conceder acesso de leitura à conta que fará a integração. Até lá, distribuição aos jogadores permanece pendente; a atualização instalada continua pelo Setup recebido externamente.

## Contrato GitHub Releases v1 (proposto)

- Configuração por ambiente: `GIM_GITHUB_RELEASES_OWNER`, `GIM_GITHUB_RELEASES_REPO`, `GIM_GITHUB_RELEASES_CHANNEL` e `GIM_GITHUB_RELEASES_PUBLIC_KEY` (chave pública Ed25519 codificada em Base64, 32 bytes). `GIM_GITHUB_RELEASES_MANIFEST_ASSET` seleciona o asset JSON e, por padrão contratual, é `gim-release.json`.
- Canal `stable` usa releases estáveis; canais como `beta` usam releases prerelease. A tag segue `<channel>-v<version>` (por exemplo, `stable-v1.2.3` ou `beta-v1.2.3`). Owner, repositório, canal e chave não têm valores padrão; manifesto com nome inválido também bloqueia a configuração.
- Cada release contém o asset JSON do manifesto e o asset de assinatura destacado `<manifesto>.sig`. A assinatura Base64 Ed25519 cobre os bytes exatos do manifesto. O manifesto UTF-8 contém `schema_version` (inteiro `1`), `app_id` (`guild-idle-manager`), `version` (SemVer), `channel`, `minimum_supported_version`, `asset_name` (nome do instalador anexado à mesma release) e `asset_sha256` (64 caracteres hexadecimais minúsculos). Releases devem marcar prerelease de acordo com o canal.
- O cliente deve conferir canal/tag, esquema, app id, SemVer, versão mínima, presença do asset, assinatura pela chave configurada e SHA-256 antes de oferecer ou aplicar qualquer pacote. Qualquer inconsistência, campo ausente, erro de rede ou assinatura/hash inválido falha sem download/execução/aplicação. Aplicar o pacote exige etapa separada com staging, backup dos dados locais, fechamento gracioso, substituição atômica e rollback.
- Esta versão implementa somente interface de configuração, validação e estado fail-closed exibido em `/updates`; não implementa consumo HTTP, verificação criptográfica do manifesto, download ou instalação. `GET /updates/check` em pacote instalado relata a origem e a razão da desativação sem consultar o GitHub. O verificador e aplicador só podem ser habilitados em entrega posterior com contrato e publicação confirmados.

## Requisitos para distribuição

Antes de ativar atualização automática de produção via GitHub Releases, definir o contrato do asset/manifest versionado, assinatura criptográfica validada com chave pública empacotada, hash do pacote, compatibilidade de plataforma e versão mínima, download para área temporária, verificação antes da instalação, cópia dos dados locais, troca atômica do pacote e rollback recuperável. O instalador de produção deve preservar o perfil de campanha e só migrar os dados após a cópia de segurança. Nenhum desses serviços de distribuição faz parte desta versão.
