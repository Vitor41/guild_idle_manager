# Validação da correção 0.5.4 — carne e navegação lateral

## Resultado

- Carne: o catálogo reativa um material de carne elegível para guildas nível 1 mesmo quando materiais de carne de nível superior permanecem ativos. Produção de 60 segundos chega ao inventário e é exibida nas páginas de inventário e coleta.
- Navegação: em desktop, a barra lateral inteira rola quando seu conteúdo excede a altura da janela. Em telas estreitas, a navegação compacta mantém seu próprio scroll.
- Coleta ao vivo: a tela consulta `/gathering/status` a cada 15 segundos e atualiza quantidade por família, armazém e progresso sem recarregar a página. Ao entrar no inventário, a coleta pendente é processada antes da renderização. O polling encontra a tela atual após navegação interna e ignora respostas atrasadas para uma tela já substituída.

## Evidência visual

Capturas realizadas no servidor e perfil temporários, sem usar saves do usuário. As imagens incluem a regressão reproduzida com o layout anterior e a correção em 1920×620 e 1920×1080:

- `evidence_0.5.4/sidebar-before-0.5.3-1920x620.png`
- `evidence_0.5.4/sidebar-before-0.5.3-1920x1080.png`
- `evidence_0.5.4/sidebar-after-0.5.4-1920x620.png`
- `evidence_0.5.4/sidebar-after-0.5.4-1920x1080.png`
- `evidence_0.5.4/sidebar-dom-results.json`

Nos dois tamanhos, a validação DOM confirmou `overflow-y: auto`, o link “Atualizações” inteiramente dentro da barra lateral e o clique abrindo `/updates`. Antes da correção, o link ficava abaixo da área visível com `overflow-y: hidden`.

## Verificações

- `tests.test_campaign_content_versioning tests.test_gathering_service tests.test_stage5_ui_contracts tests.test_desktop_art tests.test_desktop_http_smoke`: 52 testes aprovados, incluindo smoke HTTP.
- `tests.test_desktop_http_smoke`: 1 teste aprovado.
- `compileall` de `app` e `tests`: aprovado.
- `git diff --check`: aprovado.

Não foi executado build nem instalação nesta rodada.
