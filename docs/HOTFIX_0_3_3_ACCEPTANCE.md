# Aceite do hotfix 0.3.3

## Correção

O botão de evolução de construção enviava o formulário para `/buildings`, pois `button.formAction` contém o fallback da ação do formulário mesmo quando o botão não declara `formaction`. O navegador enviava `POST /buildings` e recebia 405. O JavaScript agora usa `form.action` como padrão e só lê `button.formAction` quando existe o atributo `formaction`.

Os registros de diagnóstico não bloqueiam mais o envio da ação. A chamada de telemetria tem limite de 750 ms, e erros de caminho de log são ignorados para preservar a resposta do jogo.

## Evidências

- Reprodução do código 0.3.2: o clique enviou `POST /buildings` e não alterou o save.
- Smoke de navegador com o código corrigido: `POST /buildings/1/upgrade` retornou 303 para a página de Construções. No SQLite isolado, o prédio ficou no nível 1 e o tesouro passou a 90 ouro. O log de staging correlacionou clique, início e resultado com a mesma referência.
- `APP_MODE=desktop`, `DATABASE_URL=sqlite:///:memory:`: `python -m unittest tests.test_desktop_http_smoke tests.test_stage5_ui_contracts tests.test_gameplay_diagnostics -v` passou 20/20.
- O smoke HTTP cobre coleta, contratos sem e com preparo, masmorras, chefes e persistência. O contrato da interface também verifica a escolha correta entre `action` e `formaction`.

## Distribuição

O Setup não foi gerado nem executado. O build DEV aguarda o valor de `GIM_RELEASE_PUBLIC_KEY_B64` já configurado no GitHub. Embutir outra chave impediria a verificação das futuras releases assinadas pelo segredo oficial. Depois de fornecer a chave pública, gere o Setup em staging, assine o manifesto com o par oficial e publique somente após integrar este commit ao branch padrão e configurar o ambiente Actions `release-signing`.
