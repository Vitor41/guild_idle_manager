# Atualização do aplicativo

Versão local atual: `0.2.0` (`app/core/version.py`, também publicada como `FastAPI.version`), primeiro incremento menor desde `0.1.0`. Incrementos seguintes de funcionalidade usam `0.1` na versão menor; a versão major fica reservada a mudança arquitetural/de design relevante ou lançamento de plataforma. A tela `/updates` exibe essa versão. No modo DEV, **Verificar versão do checkout** lê localmente o `APP_VERSION` do checkout; se estiver acima da versão carregada, a ação segura é fechar e reiniciar `Iniciando_jogo_dev.bat`. O fluxo já existente executa o checkout local, exige reinício para mudanças Python e permite `Ctrl+R` para Jinja/CSS/JS.

## Situação

O projeto não contém feed de lançamentos, manifest assinado, verificação de assinatura/checksum, pacote de atualização, serviço de instalação ou mecanismo de rollback. A tela não finge que uma atualização remota foi verificada e não baixa executáveis.

## Requisitos para distribuição

Antes de ativar atualização automática, definir um endpoint de manifesto versionado, assinatura criptográfica validada com chave pública empacotada, hash do pacote, compatibilidade de plataforma e versão mínima, download para área temporária, verificação antes da instalação, cópia dos dados locais, troca atômica do pacote e rollback recuperável. O instalador deve preservar o perfil de campanha e só migrar os dados após a cópia de segurança. Nenhum desses serviços de distribuição faz parte desta versão.
