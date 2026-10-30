# Melhorias lote 1 — orientação visual DA

**Escopo:** ranking, inventário, Guia de Classes, preparação da Vigília e contador de coleta. **Base:** `DESKTOP_VISUAL_SYSTEM.md`, `GAMEPLAY_EVOLUTION_VISUAL_SYSTEM.md`, `REGIONAL_SUPPLY_PREPARATION_VISUAL_SPEC.md` e `GDD_EVOLUCAO_GAMEPLAY.md`. Dados e decisões de regra vêm do runtime; exemplos de composição não definem balanceamento. O aceite visual do aplicativo instalado cabe ao usuário.

## Regras comuns

Preservar a linguagem **Sala de Comando**: superfícies sólidas `--surface`/`--surface-hi`, texto `--text`, divisórias `--border`, ouro `--gold` para ação principal e verde/azul/vermelho com rótulo de estado. Títulos em Georgia, interface em Segoe UI e números em `font-variant-numeric: tabular-nums`. Arte fica em hero ou cartão narrativo; tabela, barra, custo e timer ficam sobre fundo sólido. Usar sprites locais de 64 px em linhas e 128 px apenas quando o tamanho do componente justificar. Nenhuma imagem nova é necessária para este lote.

## Ranking de guildas

Referência de conteúdo: `design/preview/evolution-vigilia.html` (`#ranking`); regra: GDD §18 e pontuação persistente 50% influência, 25% reputação, 25% vitórias em eventos. Converter a lista demonstrativa em **tabela semântica** para leitura horizontal: posição, guilda, região ou perfil, influência, reputação, vitórias e pontuação total. Alinhar números à direita e usar algarismos tabulares; cabeçalho e unidade visíveis. Destacar a linha da guilda do jogador com fundo elevado e rótulo “Sua guilda”, sem depender só da cor. Uma explicação curta de como a pontuação é formada deve ficar junto ao título, com pesos vindos da configuração real se ela for exibida. Ordenação, empate, período e atualização após a Vigília devem corresponder ao backend; não animar mudanças de posição como se fossem recompensa. Em janela estreita, manter nome/posição/pontos identificáveis e permitir rolagem horizontal da tabela com pista visível; não cortar colunas silenciosamente.

## Inventário compacto

Referências: `design/preview/inventory.html` e seção “Inventário denso” de `DESKTOP_VISUAL_SYSTEM.md`. Manter resumo e filtros antes da lista/grade; KPI **Equipamentos** separado de materiais acumuláveis. Para materiais, uma barra curta pode representar **quantidade frente à capacidade real aplicável**; mostrar sempre `atual / limite` em texto. Se não existir limite por item, não inventar porcentagem: mostrar apenas quantidade e uma barra geral do Armazém, se houver capacidade global. Para equipamentos únicos, representar contagem em texto, raridade em badge, instância/atributos/proprietário no detalhe; barra só se houver denominador real de slots/capacidade, identificado no rótulo. Nome pode ocupar duas linhas estáveis com título completo acessível. Slots de 58 px e sprites de 64 px já cobrem o catálogo. Barras não devem competir com o nome nem sugerir progresso de qualidade ou poder inexistente. Estado cheio/sem espaço inclui texto e próximo passo.

## Âncoras do Guia de Classes

Usar **o mesmo padrão do Guia do Jogo**: `app/templates/guide/index.html` (`nav.guide-index`) e `app/static/css/main.css` (`.guide-index`, `.guide-section` e `scroll-margin-top`). O Guia de Classes já tem seis destinos `#guia-classes`, `#guia-habilidades`, `#guia-atributos`, `#guia-combinacoes`, `#guia-coleta`, `#guia-dungeons`; preservar IDs e rótulos. Cada link deve chegar ao título da seção visível abaixo da barra fixa. “Classes” precisa apontar para uma seção nomeada com título, em vez de um `div` vazio isolado. Links ficam em uma linha rolável na janela estreita, com alvo mínimo de 40 px, foco de 3 px, `aria-label` no `nav` e estado atual somente quando a seção ativa for conhecida. Evitar um segundo estilo de abas ou rolagem animada obrigatória; respeitar movimento reduzido e o histórico do navegador.

## Preparação e andamento da oferta da Vigília

Referência: `design/preview/evolution-vigilia.html` (`#offer-detail`) e `REGIONAL_SUPPLY_PREPARATION_VISUAL_SPEC.md`. No diálogo/cartão, apresentar rank, duração, chance base/final, risco, recompensa e equipe antes da ação. A escolha de **um suprimento opcional por grupo** fica depois da equipe e antes de iniciar, com custo, saldo/elegibilidade, bônus de +5 pontos percentuais e chance final legíveis; seleção obsoleta ou recursos insuficientes desabilitam o início com motivo próximo, sem perder a equipe escolhida. O backend confirma custo e snapshot.

Após iniciar, substituir a ação de preparo pelo estado **Em andamento**: horário previsto, tempo restante textual e barra de progresso derivada de início/fim persistidos. Mostrar o progresso como informação, sem prometer coleta automática. Quando o tempo terminar, usar **Concluída · pronta para coleta** e ação de coleta/resultado conforme a regra da oferta. Distinguir timer encerrado de prêmio já resgatado; após coleta, mostrar **Coletada** e resumo/histórico, sem botão repetido. Em erro de sincronização ou relógio, mostrar estado textual e dados confirmados pelo serviço. Não colocar cena atrás de custo, timer ou resultado. O diálogo deve prender foco enquanto aberto, fechar por ação clara e devolver foco ao acionador.

## Contador de coleta

Referências: `design/preview/evolution-campaigns.html`, cena `gathering-worksite.webp` e sprite `gathering-kit.png`. Cada tarefa mostra família/nó, trabalhador designado, produção acumulada, próximo ciclo, capacidade e estado. O número pode transitar discretamente **uma vez quando um ciclo confirmado altera o total** (até cerca de 300 ms); a animação não calcula nem antecipa produção. Valor final e `aria-label` permanecem disponíveis imediatamente; `prefers-reduced-motion: reduce` elimina transição. Não anunciar cada segundo nem cada quadro do contador: `aria-live` apenas para mudança relevante, como lote coletado, pausa por Armazém cheio ou retorno de produção. Barra de ciclo usa tempo persistido e rótulo textual; barra de capacidade usa `atual / limite`. Em pausa, mostrar “Armazém cheio”, manter o trabalhador designado e oferecer caminho para liberar espaço. Atualização offline em lote deve mostrar total final e origem, sem reproduzir uma sequência longa de contagens.

## Checagem de integração

- Tabela compreensível com teclado, leitor de tela, zoom 200% e janela de 420 px; linha do jogador identificável sem cor.
- Barras têm denominador verdadeiro e texto equivalente; equipamento único nunca parece pilha de materiais.
- Todas as seis âncoras do Guia de Classes levam a títulos visíveis; foco e botão Voltar do navegador funcionam.
- Oferta cobre disponível, sem recursos, em andamento, concluída e coletada; suprimento e timer usam o estado real do backend.
- Contador de coleta não salta layout, não anuncia segundos e fica estático com movimento reduzido.
