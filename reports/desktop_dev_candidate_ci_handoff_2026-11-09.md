# Handoff: validação de candidato DEV sem publicar release

## Objetivo

Adicionar validação manual de um commit candidato por SHA exato, incluindo build do pacote DEV, execução dos smokes do app e instalação do Setup final num perfil descartável. O fluxo não cria GitHub Release e não usa chave privada no job que executa o binário candidato.

## Fluxos adicionados

- `build-dev-candidate.yml` recebe um SHA completo, exige correspondência com a revisão selecionada e com o checkout, valida a versão SemVer, constrói o pacote no Windows Server 2025 e executa `validate_desktop_setup_candidate.ps1`.
- A validação instala o Setup sob `RUNNER_TEMP`, cria um save-fixture nesse perfil, compara o hash antes/depois e executa `--version`, `--smoke` e `--launcher-smoke` na cópia instalada.
- O job de build tem somente permissão `contents: read`, não acessa qualquer segredo de assinatura e envia artifact de curta duração com metadados, hashes e evidência. Nenhum job privilegiado consome seu artifact.
- O Setup de candidato permanece sem assinatura de release. A assinatura só acontece no workflow existente de publicação, que aceita tag após ela estar integrada à branch padrão. Esse workflow agora verifica localmente a assinatura Ed25519, identidade/canal/versão/nome e hash do Setup antes de publicar.
- `verify_signed_release.py` realiza a validação offline do manifesto assinado, sem depender da API remota.
- O workflow de publicação existente aponta para o ambiente `release-signing` e só publica tags já integradas ao branch padrão. A configuração de revisores obrigatórios e branches permitidas desse Environment não é legível pelo checkout; confirme essas proteções no GitHub antes de publicar.

## Como executar depois de disponibilizar os workflows

O arquivo de build precisa estar na branch padrão para que o GitHub permita `workflow_dispatch`. Após a aprovação e integração desta infraestrutura, selecione a branch candidata e informe em `candidate_commit_sha` o SHA completo da revisão exata. O job aceita somente quando o valor coincide com a revisão selecionada e com o checkout. O Setup e o ZIP ficam em artifacts temporários por três dias, sem assinatura de release e sem publicação.

O release assinado continua sendo outro fluxo: somente após revisão/integração e criação de uma tag DEV ancestral ao branch padrão, o workflow de publicação acessa a chave e valida o manifesto antes de publicar. Não execute esse fluxo para testar um candidato.

## Validação local desta entrega

- A análise sintática do PowerShell em `scripts/validate_desktop_setup_candidate.ps1` não encontrou erros.
- As invariantes conferidas localmente confirmam que o build-only não tem `workflow_run`, chave privada ou publicação; o verificador está apenas no fluxo de release antes do passo de publicar.
- `git diff --check` passou antes dos commits desta correção.
- Os testes focados de assinatura e contratos dos workflows não puderam importar `cryptography.hazmat.primitives`: o runtime Python local falha ao carregar `_rust` (`ImportError: DLL load failed`). O Python embeddable também não encontra os pacotes bloqueados em `.validation-site-packages-080` (acesso negado). O ambiente local não fornece `actionlint` nem o launcher `py`.
- O Setup 0.8.0 do SHA candidato ainda não foi construído nem instalado: este checkout não consegue reproduzir o runner Windows suportado e o workflow novo precisa primeiro estar disponível na branch padrão. O fluxo build-only acima fará essa validação no runner; não houve uso de perfil ou save real, push, dispatch, publicação ou instalação nesta entrega.

## Arquivos da entrega

- `.github/workflows/build-dev-candidate.yml`
- `scripts/validate_desktop_setup_candidate.ps1`
- `scripts/verify_signed_release.py`
- `requirements-desktop-dev.txt`
- `tests/test_publish_dev_release_workflow.py`
- `tests/test_release_signing_tool.py`
- `reports/desktop_dev_candidate_ci_handoff_2026-11-09.md`
