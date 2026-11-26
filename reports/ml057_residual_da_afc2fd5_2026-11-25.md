# ML-057 / F16 compartilhado — fechamento visual residual N2/N4

> Cópia sanitizada para versionamento em 2026-11-26. Evidências sintéticas locais, scripts, resultados brutos e capturas permanecem fora do Git; parecer, medidas, SHAs, falhas e limites foram preservados.

Data:2026-11-25. Candidato `afc2fd5a2cf6f29f774b5740cc39d4752eeff26f`. **Gate visual residual aprovado no escopo abaixo.** Os dois resíduos comunicados pelo CR e confirmados pela DA no0d1e52 estão corrigidos. Não substitui revisão técnica independente nem aceite do usuário. F16 aqui não aprova ML-056 inteira, e F33 não foi incluído nesta rodada.

| Critério | Evidência no navegador | Resultado |
| --- | --- | --- |
| Original retirado, só substituto | Em1440/390/720: preparado17, FormData[18], ambos inícios disabled=true. Mensagem: “A equipe original do preparo deve permanecer; adicione reforços sem substituir integrantes preparados.” Não anuncia possibilidade de início. | Passou |
| Original mais reforço válido | FormData[17,18], limite1–2: preparado bloqueado e sem suprimento habilitado, selo só no reforço selecionado. | Passou |
| Exata / vazia / acima do máximo | [17] habilita ambos com preparo pronto; [] bloqueia ambos; [17,18,19] bloqueia ambos e informa máximo2. Controles e FormData reais, sem forjar seleção ou flags do servidor. | Passou |
| Indisponível / em curso | Original ocupado conserva ID e ambos bloqueados. Preparo em curso mantém preparado bloqueado, sem suprimento disponível conforme estado autoritativo original. Snapshots JSON iguais antes/depois das interações. | Passou |
| Relatório antes de abrir | Nas3larguras: open=false, display=none, checkVisibility=false após GET /regional. | Passou |
| Relatório aberto e rolado |24linhas CPU; corpo rola965px em1440/720 e1007px em390. Título y86,03; fechar superior y55/40px; footer y789, todos dentro do diálogo y45–855. Sem overflow horizontal do diálogo; tabela tem rolagem local. | Passou |
| Fechar / Escape / foco | Nas3larguras, ambos removem open, deixam checkVisibility=false e devolvem foco ao botão report-1. Não confundir apenas open=false com ocultação: visibilidade foi medida também. | Passou |
| Dados do relatório | Null preserva “não registrado”, zero real preserva0. Deltas40→45/+5p.p.,30→28/−2p.p.,100→102/+2;24guildas e4etapas conservadas. | Passou |

N1/grade e N3/nome-selo permanecem fechados pelo relatório ml057_residual_da_0d1e52f_2026-11-25.md; não foram reabertos. F30/F31/F35/F36 e F17/F32 são reaproveitados dos gates anteriores, sem alegar nova auditoria geral. F03/F06 mantêm relatório separado. O aceite visual desta fatia de ML-057 e F16 compartilhado fica delimitado pela união desses relatórios e pelas limitações registradas; não declara aprovação global dos dois lotes nem de alterações paralelas ML-056.

## Evidência e limites

Chrome headless em1440/390/720CSSpx;720 é reflow equivalente a200% de1440, não zoom nativo WebView2. Captura e medidas reais de layout; captura local de relatório rolado foi inspecionada visualmente. Execução do navegador com permissão ampliada já aprovada por limitação de processo gráfico do ambiente restrito.

Harness descartável reaproveitado: preparo por POST real do serviço, somente ajustes temporais/ocupação na cópia. Histórico SQL controlado de apresentação com24planos/null/zero e ciclo completed; não valida fechamento econômico ou simulação CPU real. Não iniciou missão, coletou ou gastou. Nenhum save real/instalação. Sem alteração de runtime/branch/commit. Checkout no candidato ao iniciar; templates/estáticos fixados via git show, CSS/JS servidos também conferidos por HTTP/hash-object.

Evidências sintéticas locais: scripts de reteste, resultados de seleção e relatório e capturas focais nas três larguras. Permanecem fora do Git. Perfil descartável encerrado após captura; sem publicação.

| Arquivo | Blob |
| --- | --- |
| app/static/css/desktop-evolution.css | `1e1398e26898ef1ce60d6a267c4a49ee43f30b69` |
| app/static/js/regional-supply.js | `7200df9e32189c449c7a76720ee8611f338dab49` |
| app/templates/components/regional_offer_actions.html | `8ce3d7e0b535e70d9754d45b282151c7dcf51c05` |
| app/templates/regional/index.html | `32442efb4c785e7105b2b3c0c4e9ddb0154bd4ac` |
