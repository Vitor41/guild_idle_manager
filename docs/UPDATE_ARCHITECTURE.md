# Atualização do aplicativo

Versão local atual: `0.2.0` (`app/core/version.py`, também publicada como `FastAPI.version`), primeiro incremento menor desde `0.1.0`. Incrementos seguintes de funcionalidade usam `0.1` na versão menor; a versão major fica reservada a mudança arquitetural/de design relevante ou lançamento de plataforma.

## DEV a partir do checkout

A tela `/updates` oferece **Verificar versão do checkout**. O endpoint lê `APP_VERSION` dos arquivos já presentes no checkout, sem importar ou executar o arquivo. Quando a versão em disco for superior à carregada, **Reiniciar e aplicar versão do projeto** solicita o fechamento da janela; o launcher encerra o servidor e executa o hook normal de shutdown/saves, libera o mutex e inicia novamente `sys.executable -m app.desktop` a partir da raiz deste checkout. Assim o processo recarrega os arquivos Python, templates, CSS e JavaScript já existentes no disco. Essa ação não busca código, não executa `git pull`, não baixa nem substitui arquivos. Não há origem Git remota configurada neste checkout. O botão não aparece no modo frozen.

## Atualizar a cópia instalada DEV

Pacotes `sys.frozen` não têm feed nem atualizador: a aplicação mostra a versão empacotada e declara que não sabe se há versão mais recente; ela não oferece a ação de reinício do checkout. Para atualizar uma instalação DEV gerenciada, é necessário receber `GuildIdleManager-DEV-Setup.exe` por um canal confiável, fechar o jogo e executar o Setup sobre a instalação DEV existente. O script atual instala os arquivos em `%LOCALAPPDATA%\Programs\GuildIdleManager` e os saves permanecem separados em `%LOCALAPPDATA%\GuildIdleManager\saves`; o script não migra nem substitui essa pasta de dados. O Setup troca os arquivos do app com staging e backup temporário, mas só aceita a instalação que contém seu marcador DEV. Este fluxo manual não foi executado nesta entrega.

## Situação

O projeto não contém feed de lançamentos, manifest assinado, verificação de assinatura/checksum, pacote de produção nem serviço de instalação automática. A ação local reinicia o checkout já alterado no disco; ela não atualiza a fonte. Distribuição a jogadores continua pendente de definir e configurar uma origem (endpoint/feed ou canal de publicação) e publicar o pacote apropriado. Não há URL/canal configurado para obter o Setup DEV.

## Requisitos para distribuição

Antes de ativar atualização automática de produção, definir um endpoint de manifesto versionado, assinatura criptográfica validada com chave pública empacotada, hash do pacote, compatibilidade de plataforma e versão mínima, download para área temporária, verificação antes da instalação, cópia dos dados locais, troca atômica do pacote e rollback recuperável. O instalador de produção deve preservar o perfil de campanha e só migrar os dados após a cópia de segurança. Nenhum desses serviços de distribuição faz parte desta versão.
