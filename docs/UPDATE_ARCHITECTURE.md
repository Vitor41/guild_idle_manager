# Atualização do aplicativo

Versão local atual: `0.2.0` (`app/core/version.py`, também publicada como `FastAPI.version`), primeiro incremento menor desde `0.1.0`. Incrementos seguintes de funcionalidade usam `0.1` na versão menor; a versão major fica reservada a mudança arquitetural/de design relevante ou lançamento de plataforma.

## DEV a partir do checkout

A tela `/updates` oferece **Verificar versão do checkout**. O endpoint lê o `APP_VERSION` local sem importar ou executar o arquivo; se a versão do disco for superior à carregada, a aplicação orienta fechar e reiniciar `Iniciando_jogo_dev.bat`. O launcher executa o checkout corrente; mudanças em Jinja/CSS/JS podem ser aplicadas com `Ctrl+R`, e mudanças Python exigem reiniciar o processo. Não há download do código, `git pull` nem substituição da pasta fonte enquanto está em uso.

## Atualizar a cópia instalada DEV

Pacotes `sys.frozen` não têm feed nem atualizador: a aplicação mostra a versão empacotada e declara que não sabe se há versão mais recente. Para atualizar uma instalação DEV gerenciada, o jogador precisa receber `GuildIdleManager-DEV-Setup.exe` por um canal confiável, fechar o jogo e executar o Setup sobre a instalação DEV existente. O script atual instala os arquivos em `%LOCALAPPDATA%\Programs\GuildIdleManager` e os saves permanecem separados em `%LOCALAPPDATA%\GuildIdleManager\saves`; o script não migra nem substitui essa pasta de dados. O Setup troca os arquivos do app com staging e backup temporário, mas só aceita a instalação que contém seu marcador DEV. Este fluxo manual não foi executado nesta entrega.

## Situação

O projeto não contém feed de lançamentos, manifest assinado, verificação de assinatura/checksum, pacote de produção nem serviço de instalação automática. A tela não finge que uma atualização remota foi verificada e não baixa executáveis. A distribuição precisa publicar um novo Setup DEV para o fluxo manual acima; não há URL/canal configurado para obtê-lo.

## Requisitos para distribuição

Antes de ativar atualização automática de produção, definir um endpoint de manifesto versionado, assinatura criptográfica validada com chave pública empacotada, hash do pacote, compatibilidade de plataforma e versão mínima, download para área temporária, verificação antes da instalação, cópia dos dados locais, troca atômica do pacote e rollback recuperável. O instalador de produção deve preservar o perfil de campanha e só migrar os dados após a cópia de segurança. Nenhum desses serviços de distribuição faz parte desta versão.
