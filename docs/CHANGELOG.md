# Histórico de alterações

## 0.9.0 — Progressão, oficinas e economia

- Consolida melhorias aprovadas para eventos regionais, busca/exportação do Guia, indicadores de trabalho, oficinas e fluxo de atualização.
- Corrige a conclusão de trabalho das Oficinas em campanhas legadas sem fuso horário e mantém referências de diagnóstico correlacionadas.
- Permite substituir equipamento no mesmo gesto e escolher explicitamente entre anéis ou brincos quando ambos os espaços estão ocupados.
- Trata o nível de mercenário como recomendação em missões, masmorras e chefes, preservando os demais requisitos.
- Fecha os ciclos lucrativos entre Docas, desmontagem, crafting e Market; mantém as taxas de desmontagem de 50/150/300 ouro.
- Risco de balanceamento a avaliar em jogo: os pisos contra arbitragem podem elevar bastante os preços de equipamentos avançados e de algumas receitas.

## 0.8.0 — Launcher, Mercado e equipamentos

- Abre um launcher independente antes da seleção de campanhas, com verificação de atualização assinada, progresso e opções para adiar ou usar a versão instalada quando compatível.
- Restringe Atualizações dentro da campanha à consulta de versão e encaminha a instalação ao launcher.
- Move os prazos-base de venda para o Guia, melhora os cards do Mercado e confirma o estado e nome do arquivo na exportação Markdown.
- Exibe detalhes do equipamento equipado em painel contextual acessível, sem recalcular bônus.

## 0.7.1 — Correção da inicialização desktop

- Inclui `python-multipart` no pacote para processar formulários das Oficinas sem falha na abertura.
- Bloqueia a publicação de releases cujo executável não passe no teste de inicialização empacotada.

## 0.7.0 — Lotes de economia, oficinas, guia e equilíbrio regional

- Adiciona novas opções de mercado e coleta, com cancelamento de ofertas e fontes de materiais integradas à progressão; remove a cota móvel de venda de materiais.
- Permite preparar lotes temporizados nas oficinas e consultar as fontes de materiais no jogo.
- Amplia o Guia do Jogo com catálogo pesquisável de equipamentos e materiais e exportação em Markdown.
- Ajusta equipamentos e contratos regionais para equilibrar bônus, poder e risco da estratégia da CPU; corrige a elegibilidade de eventos regionais.
- Inclui correções e ajustes de interface nos fluxos de suprimentos, navegação, Vigília e atualizações.

## 0.3.1 — Hotfix de ações de gameplay e diagnóstico

- Reativa cotações e timers de suprimento após navegação assíncrona para a Vigília; preserva `formaction` ao preparar e mostra erro com referência quando uma requisição falha.
- Registra ações de coleta e ofertas regionais em `%LOCALAPPDATA%\GuildIdleManager\logs\gameplay-actions.log`, com rotação e redação de dados sensíveis.
- Confirma início de missões, contratos regionais, masmorras e chefes sem prédios construídos; construções continuam concedendo bônus, sem bloquear os inícios.
- Define `Vitor41/guild_idle_manager` como origem padrão do canal DEV, mantendo atualização desativada enquanto não houver chave pública Ed25519 confiável e release assinada.
- Empacota owner/repo e chave pública opcional no config de distribuição; builds DEV aceitam overrides explícitos e slugs inválidos são recusados, com compatibilidade para bundles 0.3.1 anteriores.
- A build 0.3.0 sem chave pública precisa de um Setup bootstrap instalado manualmente antes de receber atualizações assinadas.

## 0.3.0 — Lote de melhorias 2

- Corrige a leitura de timestamps UTC sem fuso no navegador e mantém a duração da Vigília em seis horas.
- Mantém selecionável o suprimento opcional durante a consulta de equipe, permitindo iniciar sem suprimento quando a cotação não está disponível.
- Exibe saldo de estamina, teto, taxa e progresso confirmado de recarga junto à ação Modo Offline, com ajuda por foco, clique/toque e hover.
- Alinha o índice de Classes ao Guia do Jogo, com âncoras focáveis, estado ativo e suporte a movimento reduzido.
- Preserva a atribuição de trabalhadores de coleta e seus estados de capacidade.

Esta rodada não gerou build nem instalador e não alterou a instalação ou os saves do jogador. Use a validação automatizada registrada na matriz; a inspeção visual e a instalação ficam para a etapa manual do usuário.
