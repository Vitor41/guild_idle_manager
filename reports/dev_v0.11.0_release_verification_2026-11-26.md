# Verificação da publicação DEV-v0.11.0

**Registro sanitizado para o Git.** Não contém caminhos locais, capturas, arquivos baixados, chaves ou dados de saves. As verificações de artefatos foram executadas pela coordenação sobre os assets publicados.

## Publicação

- **Versão/canal:** `DEV-v0.11.0`, prerelease.
- **Data de publicação:** 2026-11-26 às 21:23:32 UTC.
- **Pull request:** [#25](https://github.com/Vitor41/guild_idle_manager/pull/25).
- **Merge e tag:** commit `2cadd4451eaee5d1a122743338b81d0e80c62146`; tag `DEV-v0.11.0` neste merge.
- **Release:** [DEV-v0.11.0](https://github.com/Vitor41/guild_idle_manager/releases/tag/DEV-v0.11.0).
- **Workflow:** [45897483540](https://github.com/Vitor41/guild_idle_manager/actions/runs/45897483540) terminou com sucesso em 2m47s. Os smokes do pacote, campanha e launcher passaram.

## Assets publicados

| Asset | Tamanho | SHA-256 |
| --- | ---: | --- |
| Setup | 69.263.360 bytes | `ec7c75635b0dc24a9ac90b82ca9d9c512c4e00c2f4e2211ab8106b76c33f3e7e` |
| Manifesto | 249 bytes | `11d62c098862e334be735c0f50c08e951568b863812faac0076efa00997e6c76` |
| Assinatura | 88 bytes | `5d75b38dc80f0d0664c57c44ae24a4186b7d78d9fe380bc1b6514822ee4c80db` |

A coordenação executou `scripts/verify_signed_release.py` nos três assets publicados. O verificador reportou `VERIFIED DEV 0.11.0`, confirmou a assinatura Ed25519 do manifesto, identidade/canal/versão, versão mínima `0.3.1` e o SHA-256 do Setup. Os hashes calculados coincidiram com os metadados publicados no GitHub.

A assinatura Ed25519 protege o manifesto e permite verificar a identidade e os hashes declarados. Isso não é assinatura Authenticode do executável nem assinatura GPG da tag.

## Gates do pacote

- O CR aprovou sem achados a integração final; o parecer está registrado no SHA `f7d61bfcdaa7ae3b4c9191347eaaba65fc4cc8e0`.
- A DA aprovou B7 no candidato cumulativo `2669ec2f809657dc309b591117ac1086b11e5853`.
- A suíte Node final passou 81/81, sem falhas ou skips.
- O pacote ML-052–057 foi entregue nesta publicação. A validação manual do usuário pode ocorrer depois e não é pendência de desenvolvimento.

## Limites

Nenhum Setup foi aberto ou instalado localmente e nenhum save real foi alterado. Os resultados de verificação acima dizem respeito aos assets publicados e aos hashes/metadados correspondentes. O relatório não atribui aceite novo a ML-028, ML-045 ou BUG-014; o aceite existente de BUG-013 permanece preservado. A limitação documentada da suíte Python ampla e as ressalvas das simulações continuam em vigor.
