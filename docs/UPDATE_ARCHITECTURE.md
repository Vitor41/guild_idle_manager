# Atualização do aplicativo

Versão local atual: `0.2.0` (`app/core/version.py`, também publicada como `FastAPI.version`), primeiro incremento menor desde `0.1.0`. Incrementos seguintes de funcionalidade usam `0.1` na versão menor; a versão major fica reservada a mudança arquitetural/de design relevante ou lançamento de plataforma.

## DEV a partir do checkout

A tela `/updates` oferece **Verificar versão do checkout**. O endpoint lê `APP_VERSION` dos arquivos já presentes no checkout, sem importar ou executar o arquivo. Quando a versão em disco for superior à carregada, **Reiniciar e aplicar versão do projeto** solicita o fechamento da janela; o launcher encerra o servidor e executa o hook normal de shutdown/saves, libera o mutex e inicia novamente `sys.executable -m app.desktop` a partir da raiz deste checkout. Assim o processo recarrega os arquivos Python, templates, CSS e JavaScript já existentes no disco. Essa ação não busca código, não executa `git pull`, não baixa nem substitui arquivos. Não há origem Git remota configurada neste checkout. O botão não aparece no modo frozen.

## Atualizar a cópia instalada DEV

Pacotes `sys.frozen` não têm feed nem atualizador: a aplicação mostra a versão empacotada e declara que não sabe se há versão mais recente; ela não oferece a ação de reinício do checkout. Para atualizar uma instalação DEV gerenciada, é necessário receber `GuildIdleManager-DEV-Setup.exe` por um canal confiável, fechar o jogo e executar o Setup sobre a instalação DEV existente. O script atual instala os arquivos em `%LOCALAPPDATA%\Programs\GuildIdleManager` e os saves permanecem separados em `%LOCALAPPDATA%\GuildIdleManager\saves`; o script não migra nem substitui essa pasta de dados. O Setup troca os arquivos do app com staging e backup temporário, mas só aceita a instalação que contém seu marcador DEV. Este fluxo manual não foi executado nesta entrega.

## Situação

O projeto não contém feed de lançamentos, manifest assinado, verificação de assinatura/checksum, pacote de produção nem serviço de instalação automática. A ação local reinicia o checkout já alterado no disco; ela não atualiza a fonte. **Decisão confirmada para produção: GitHub Releases.** O checkout continua sem remote Git configurado, e a conta GitHub conectada não tem acesso a um repositório Guild Idle Manager; portanto owner/repo e URL não foram confirmados e nenhuma consulta/remessa de release é ativada.

Sem owner/repo, é seguro preparar apenas a estrutura configurável: opções obrigatórias de owner/repo sem valores padrão inventados, construção da URL oficial de Releases quando ambas existirem, validação de versão/canal/asset, e comportamento explicitamente desativado sem configuração. O código não deve fazer requisições GitHub quando a origem estiver incompleta. Dependem do owner/repo confirmado e acesso ao repositório: configurar a origem real, escolher canais/prereleases e nomes dos assets, publicar o Setup/manifesto, fixar hashes/assinatura e validar o pacote publicado. O próximo passo mínimo é fornecer o owner/repo exato e conceder acesso de leitura à conta que fará a integração. Até lá, distribuição aos jogadores permanece pendente; a atualização instalada continua pelo Setup recebido externamente.

## Requisitos para distribuição

Antes de ativar atualização automática de produção via GitHub Releases, definir o contrato do asset/manifest versionado, assinatura criptográfica validada com chave pública empacotada, hash do pacote, compatibilidade de plataforma e versão mínima, download para área temporária, verificação antes da instalação, cópia dos dados locais, troca atômica do pacote e rollback recuperável. O instalador de produção deve preservar o perfil de campanha e só migrar os dados após a cópia de segurança. Nenhum desses serviços de distribuição faz parte desta versão.
