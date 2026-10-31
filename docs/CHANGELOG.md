# Histórico de alterações

## 0.3.1 — Hotfix de ações de gameplay e diagnóstico

- Reativa cotações e timers de suprimento após navegação assíncrona para a Vigília; preserva `formaction` ao preparar e mostra erro com referência quando uma requisição falha.
- Registra ações de coleta e ofertas regionais em `%LOCALAPPDATA%\GuildIdleManager\logs\gameplay-actions.log`, com rotação e redação de dados sensíveis.
- Confirma início de missões, contratos regionais, masmorras e chefes sem prédios construídos; construções continuam concedendo bônus, sem bloquear os inícios.
- Define `Vitor41/guild_idle_manager` como origem padrão do canal DEV, mantendo atualização desativada enquanto não houver chave pública Ed25519 confiável e release assinada.
- A build 0.3.0 sem chave pública precisa de um Setup bootstrap instalado manualmente antes de receber atualizações assinadas.

## 0.3.0 — Lote de melhorias 2

- Corrige a leitura de timestamps UTC sem fuso no navegador e mantém a duração da Vigília em seis horas.
- Mantém selecionável o suprimento opcional durante a consulta de equipe, permitindo iniciar sem suprimento quando a cotação não está disponível.
- Exibe saldo de estamina, teto, taxa e progresso confirmado de recarga junto à ação Modo Offline, com ajuda por foco, clique/toque e hover.
- Alinha o índice de Classes ao Guia do Jogo, com âncoras focáveis, estado ativo e suporte a movimento reduzido.
- Preserva a atribuição de trabalhadores de coleta e seus estados de capacidade.

Esta rodada não gerou build nem instalador e não alterou a instalação ou os saves do jogador. Use a validação automatizada registrada na matriz; a inspeção visual e a instalação ficam para a etapa manual do usuário.
