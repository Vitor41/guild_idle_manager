# Aceite do hotfix 0.3.3

## Correção

O botão de evolução de construção enviava o formulário para `/buildings`, pois `button.formAction` contém o fallback da ação do formulário mesmo quando o botão não declara `formaction`. O navegador enviava `POST /buildings` e recebia 405. O JavaScript agora usa `form.action` como padrão e só lê `button.formAction` quando existe o atributo `formaction`.

Os registros de diagnóstico não bloqueiam mais o envio da ação. A chamada de telemetria tem limite de 750 ms, e erros de caminho de log são ignorados para preservar a resposta do jogo. A cotação de suprimentos também envia os campos como `application/x-www-form-urlencoded`, formato que o leitor de formulários da aplicação já aceita; o `multipart/form-data` enviado antes produzia uma equipe vazia.

## Evidências

- Smoke em Chromium headless, servidor local e perfil temporário: o clique de melhoria enviou `POST /buildings/1/upgrade` e recebeu 303. O SQLite mostrou construção 1 no nível 1 e ouro 990; a referência `ec2363b2-5fb1-4b4e-811c-cbe6e6715afc` correlacionou clique, recebimento, envio e resultado.
- Coleta: `POST /gathering/assign` recebeu 303; o mercenário de coleta persistiu com estado `gathering`. A referência `35e95711-c4ea-4cd1-8ddc-19bafd17ab4a` correlacionou clique, recebimento, envio e resultado.
- Contrato Rank E sem suprimento: `POST /regional/offers/71/start` recebeu 303; a oferta e a execução da missão persistiram como `in_progress`, sem preparação de suprimento. Referência `3654fa48-7020-4a57-a54d-463a78654e2d`.
- Cotação e preparo: com mercenários 3 e 4 selecionados, a cotação recebeu 200 e retornou `available: true`; preparar enviou `POST /regional/offers/72/prepare` e recebeu 303. O SQLite persistiu a equipe `3,4`, bônus de 5 p.p., custo de 1 ouro, início e conclusão da preparação; o ouro caiu de 990 para 989. Referência do preparo `90a3c84d-7115-4054-a07b-802fbc4a8596`.
- Início com suprimento preparado: após selecionar a mesma equipe, `POST /regional/offers/72/start` recebeu 303; a execução da missão e a oferta persistiram como `in_progress`. Referência `6153017d-ad38-482f-81cd-960be7e3b024`.
- Contrato, masmorra e chefe sem os prédios exigidos: em outro perfil temporário, `mission_templates` exigia `contract_office` nível 1 e os templates de masmorra/chefe exigiam `scouts` nível 1; todos os prédios da guilda permaneceram em nível 0. Mesmo assim, `POST /regional/offers/71/start`, `/regional/offers/73/start` e `/regional/offers/74/start` receberam 303. SQLite persistiu a oferta 71 e uma execução de missão e duas execuções de masmorra como `in_progress`; a soma e o máximo dos níveis de construção continuaram zero. Referências `acebe9c9-154f-438c-a6e2-fef229365bd1`, `aa932697-1713-4be5-a56a-e55ec72b4ee1` e `84afc3b4-fea0-403c-a7ff-910f72c88fe2`.
- `APP_MODE=desktop`, `DATABASE_URL=sqlite:///:memory:`: `python -m unittest tests.test_desktop_http_smoke tests.test_stage5_ui_contracts tests.test_gameplay_diagnostics -v` passou 20/20 após a correção. A validação no Chromium confirmou o corpo repetido `mercenary_ids=3&mercenary_ids=4` e resposta `available: true`.

## Distribuição

O Setup DEV local foi gerado sem ser executado em `dist/staging/gim-0.3.3-hotfix-20261101-release-candidate/GuildIdleManager-DEV-Setup.exe` (63.950.848 bytes; SHA-256 `4303B73524D9AE98B8FDC87AC24432F707D47FED414EA1AE450B796A7132798D`). O ZIP portátil ao lado tem 64.396.796 bytes e SHA-256 `80BF0C9F0056972C089DE35C6B03DB5E7C50CA9D5D59F2E175249265E995C50C`. A versão 0.3.3 foi conferida no módulo compilado `app.core.version` do PYZ da build. O gabinete IExpress do Setup foi inspecionado sem executar o instalador: contém esse mesmo ZIP (hash idêntico) e o script de instalação correspondente ao fonte. O ZIP passou na verificação CRC; o bundle contém a chave pública oficial, o JavaScript corrigido e o manifesto local de arte com SHA-256 `6bfc334b26d6b7f7cfe21ebf59539ffe2198b1b418422c357104365efe7b2afa`, cujos cinco caminhos declarados existem. O Setup tem cabeçalho PE válido e não tem assinatura Authenticode.

Não existe release publicada no GitHub para este repositório. Este artefato é um instalador local/bootstrap, não um Setup de release assinada: `gim-release.json` e `gim-release.json.sig` não foram gerados nem incluídos, então não há assinatura Ed25519 de release a validar. O fluxo de criação e verificação da assinatura exige a chave privada do segredo de release, que não foi acessada. O Setup não foi executado e nenhuma release foi publicada.

Os perfis, bancos e logs dos smokes são temporários e isolados; nenhum save de usuário foi aberto ou alterado.
