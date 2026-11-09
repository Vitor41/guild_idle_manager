# Handoff: validação de candidato DEV sem publicar release

## Objetivo

Adicionar validação manual de um commit candidato por SHA exato, incluindo build do pacote DEV, execução dos smokes do app e instalação do Setup final num perfil descartável. O fluxo não cria GitHub Release e não usa chave privada no job que executa o binário candidato.

## Fluxos adicionados

- `build-dev-candidate.yml` recebe um SHA completo, exige correspondência com a revisão selecionada e com o checkout, valida a versão SemVer, constrói o pacote no Windows Server 2025 e executa `validate_desktop_setup_candidate.ps1`.
- A validação instala o Setup sob `RUNNER_TEMP`, cria um save-fixture nesse perfil, compara o hash antes/depois e executa `--version`, `--smoke` e `--launcher-smoke` na cópia instalada.
- O job de build tem somente permissão `contents: read`, não acessa a chave privada e envia artifact de curta duração com metadados, hashes e evidência.
- `sign-dev-candidate.yml` é disparado após sucesso do build manual da mesma organização. Usa scripts da branch padrão, valida proveniência e hashes do artifact, assina e verifica o manifesto localmente, e envia artifact assinado por três dias. Não cria release nem executa o binário recebido.
- `verify_signed_release.py` verifica assinatura Ed25519, identidade/canal/versão/nome e hash do Setup sem depender da API remota.

## Como executar depois de disponibilizar os workflows

Os arquivos de workflow precisam estar na branch padrão para que o GitHub permita `workflow_dispatch` e `workflow_run`. Após a aprovação e integração desta infraestrutura, selecione a branch candidata e informe em `candidate_commit_sha` o SHA completo da revisão exata. O job aceita somente quando o valor coincide com a revisão selecionada e com o checkout. O Setup validado e o Setup assinado ficam em artifacts temporários; nenhum passo publica uma release.

## Validação local desta entrega

- A análise sintática do PowerShell em `scripts/validate_desktop_setup_candidate.ps1` não encontrou erros.
- `git diff --check` passou antes do commit.
- Os testes focados de assinatura e contratos dos workflows não puderam importar `cryptography.hazmat.primitives`: o runtime Python local falha ao carregar `_rust` (`ImportError: DLL load failed`). O Python embeddable também não encontra os pacotes bloqueados em `.validation-site-packages-080` (acesso negado). O ambiente local não fornece `actionlint` nem o launcher `py`.
- O Setup 0.8.0 do SHA candidato ainda não foi construído nem instalado: este checkout não consegue reproduzir o runner Windows suportado e os workflows novos precisam primeiro estar disponíveis na branch padrão. O fluxo build-only acima fará essa validação no runner; não houve uso de perfil ou save real, push, dispatch, publicação ou instalação nesta entrega.

## Arquivos da entrega

- `.github/workflows/build-dev-candidate.yml`
- `.github/workflows/sign-dev-candidate.yml`
- `scripts/validate_desktop_setup_candidate.ps1`
- `scripts/verify_signed_release.py`
- `requirements-desktop-dev.txt`
- `tests/test_publish_dev_release_workflow.py`
- `tests/test_release_signing_tool.py`
- `reports/desktop_dev_candidate_ci_handoff_2026-11-09.md`
