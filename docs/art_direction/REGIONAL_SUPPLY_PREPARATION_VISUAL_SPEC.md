# Suprimento opcional por grupo — especificação visual DA

**Referência:** `design/preview/evolution-vigilia.html`, diálogo “Patrulha do Portão”. O controle de exemplo usa dados ilustrativos e não consome recursos. Regras de produto: `docs/GDD_EVOLUCAO_GAMEPLAY.md` §17. Aplicar a mesma gramática a contratos, masmorras e chefes regionais, sem criar uma tela ou card adicional.

## Composição

Dentro da preparação da equipe, após a lista de mercenários e antes do botão de iniciar, inserir **uma** opção de suprimento do grupo. Uma linha mostra nome/efeito, outra mostra custo e chance resultante; uma mensagem curta anuncia o estado. O custo deve estar visível antes de confirmar a expedição e incluir ouro, materiais e esforço/tempo quando aplicáveis. O exemplo Rank E do mock (`5 ouro + 1 madeira`) não define balanceamento; o runtime deve renderizar valores validados por oferta/rank e saldo da campanha.

| Estado | Apresentação e ação |
|---|---|
| Disponível, não selecionado | Checkbox desmarcado, chance base e custo legível. Iniciar sem suprimento não desconta nada. |
| Selecionado | Checkbox marcado, borda dourada, chance base **+5 pontos percentuais** mostrada como valor final; custo permanece visível. No máximo um suprimento por expedição. |
| Sem recursos | Checkbox desabilitado, motivo textual com saldo/custo e material faltante. Chance base permanece legível; não permitir envio com opção selecionada obsoleta. |
| Indisponível | Checkbox desabilitado e motivo específico da oferta/regra; não esconder a opção nem apresentar bônus aplicável. |
| Erro ou mudança de saldo | Mostrar mensagem próxima ao controle e manter a equipe escolhida para nova tentativa. O backend confirma consumo e bônus na mesma operação de início. |

## Integração e limites

- O backend decide elegibilidade, custo por rank e valor final; a interface somente apresenta o snapshot da oferta. O custo deve **não exceder o retorno incremental esperado** do bônus de 5 p.p. segundo a simulação de balanceamento, além do limite econômico da vitória do rank. Não extrapolar o custo Rank E do mock para D–S.
- Registrar no snapshot da run o suprimento escolhido, custo debitado e efeito. A confirmação de início mostra sucesso ou erro; não aplicar chance/consumo no JavaScript.
- Em janela estreita, manter o bloco dentro do diálogo e permitir quebra da linha de custo/chance sem comprimir botões ou cards. Checkbox e resumo têm foco visível, rótulo clicável e `role="status"` apenas para mudanças relevantes; não anunciar timer por segundo.
- O bloco recolhido “Ver estados de disponibilidade” existe só para revisão da prévia. No produto, mostrar apenas o estado real da oferta. A ausência de suprimento não bloqueia a expedição.
