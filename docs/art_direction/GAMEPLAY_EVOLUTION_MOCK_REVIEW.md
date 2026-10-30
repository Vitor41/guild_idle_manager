# Revisão dos mocks da evolução de gameplay

Prévia navegável em `design/preview/`, sem build e com dados ilustrativos. Abra `evolution-campaigns.html` no navegador. A barra lateral percorre as cinco telas; **Simular janela estreita** alterna a largura da prévia. As regras de produto devem ser conferidas no `docs/GDD_EVOLUCAO_GAMEPLAY.md`.

| Tela | Arquivo | Estados para revisar |
|---|---|---|
| Campanhas e coleta | `design/preview/evolution-campaigns.html` | seleção de save, guilda/região natal, coleta ativa, trabalhador ocupado, armazém cheio, início explícito do Modo Offline; abrir os diálogos de detalhes, nova guilda, designação e armazém. |
| Vigília Regional | `design/preview/evolution-vigilia.html` | cinco regiões, 10 contratos/3 masmorras/1 chefe da região ativa, ciclo de 6 h, ranking de cinco guildas e relatório de ciclo; testar ofertas e resultado. |
| Portal e rebelião | `design/preview/evolution-events.html` | portal disponível, em andamento, expirado e resolvido; rebelião convidada, prioridade do jogador, duração de 12 h e resultados agregados/individuais; abrir avisos e relatórios. |
| Retorno offline | `design/preview/evolution-offline.html` | relatório aberto na chegada, tempo ausente e reconhecido, estamina, ouro base separado do bônus do armazém, coleta por tarefa, ciclos/eventos e alerta ClockGuard; confirmar e reabrir estados. |
| Conquistas e Códex | `design/preview/evolution-codex.html` | filtros de conquistas/Códex, progresso, bloqueio, resgate regular, resgate lendário único, registro descoberto/oculto e detalhe de item; simular o claim. |

## Gate visual

- Em desktop, conferir legibilidade, hierarquia, densidade e consistência com a identidade **Sala de Comando**.
- Em janela estreita, acionar o botão de largura e percorrer todas as seções, navegação, ações e diálogos sem corte ou sobreposição.
- Usar teclado para percorrer links, filtros, botões e diálogos; confirmar foco visível, rótulos e retorno do foco ao fechar.
- Comparar em WebView2 no tamanho real do aplicativo, com zoom e conteúdo real, antes de aprovar integração.

As capturas `desktop-theme-wide.png`, `desktop-theme-minimum.png` e `desktop-theme-missions-wide.png` não foram localizadas no workspace durante esta revisão. A comparação direta com essas imagens permanece pendente; os mocks preservam a paleta, tipografia, sprites e composição definidos na direção de arte existente.
