# Guild Idle Manager - Fluxo de Desenvolvimento

Este arquivo define o fluxo de trabalho dos agentes DEV, DA e CR no projeto.
O checkout de implementação fica em `C:\Users\vitor\Guild Idle Manager\App GIM`.

## Papéis

- **Conversa principal:** representa o usuário, define escopo, coordena etapas, acompanha evidências e decide quando uma entrega está pronta para validação do usuário.
- **DEV:** implementa as tarefas autorizadas, escreve e executa testes, atualiza documentação de status e cria commits pequenos e rastreáveis.
- **DA (Direção de Arte):** define linguagem visual, componentes, assets e critérios de interface. Não muda regras de negócio nem implementa runtime, salvo autorização explícita.
- **CR (Code Reviewer):** revisa de forma independente um commit/branch já entregue pelo DEV, priorizando bugs, regressões, segurança, integridade de dados e critérios da tarefa. Não altera código durante a revisão.

## Fluxo obrigatório de cada entrega

1. A conversa principal registra o escopo, critérios verificáveis, restrições e evidências esperadas. Quando houver trabalho visual, consulta a DA antes ou durante a implementação.
2. Antes de editar, o DEV confere a branch, o commit-base e `git status`. Arquivos de usuário, saves, credenciais, relatórios e arquivos não rastreados não relacionados devem ser preservados.
3. O DEV trabalha em uma branch própria da tarefa, dentro de `App GIM`; não cria worktrees ou cópias paralelas sem autorização.
4. O DEV implementa somente o escopo aprovado, adiciona testes proporcionais ao risco e documenta decisões, comandos, resultados e limitações.
5. Ao concluir, o DEV faz commits semânticos e entrega à conversa principal o nome da branch, hash do commit candidato, lista de arquivos, testes e matriz de critérios. Toda atividade enviada ao DEV deve incluir esta exigência.
6. A conversa principal abre/atualiza a conversa de CR e fornece branch e hash exatos. O CR revisa esse commit, não uma descrição ou estado mutável; verifica o diff e evidências de teste. O CR retorna achados priorizados com arquivo/linha e cenário de reprodução, ou declara aprovação sem achados relevantes.
7. Se houver achados, a conversa principal os encaminha ao DEV. O DEV corrige na mesma branch em novos commits, adiciona regressão e entrega novo hash. O CR revisa novamente as correções e regressões. Repetir até não haver achados bloqueantes.
8. Após aprovação técnica do CR, a conversa principal confere critérios e riscos residuais e entrega ao usuário para validação manual quando apropriado. Aprovação do CR não substitui aceite do usuário.
9. Push, PR, merge, publicação, build de distribuição ou instalação só acontecem quando autorizados explicitamente. Não usar a instalação ou saves reais do usuário para testes; preferir perfis temporários e dados isolados.

## Regras de Git e segurança

- Nunca usar `git add -A` ou staging indiscriminado. Adicionar somente arquivos pertencentes à tarefa e revisar `git diff --cached` antes de cada commit.
- Nunca apagar, limpar ou sobrescrever arquivos não rastreados sem autorização. Não incluir `.env`, chaves, logs privados, saves, bancos de campanha ou artefatos locais de teste em commits.
- Não reescrever histórico compartilhado, fazer reset destrutivo ou trocar/fechar uma branch com alterações pendentes.
- Commits do DEV devem identificar claramente a tarefa e manter o hash usado na revisão registrado na conversa principal.
- O CR deve ser independente: não implementar a correção que está avaliando. Achados devem apontar evidências concretas; sugestões sem impacto demonstrado ficam separadas de bloqueios.

## Requisitos de handoff do DEV ao CR

Cada entrega do DEV deve conter:

- branch e hash exato do commit candidato;
- resumo dos commits desde o ponto-base;
- caminhos dos arquivos alterados;
- testes executados e resultados, incluindo falhas preexistentes ou limitações;
- evidência por critério de aceitação;
- migrações, compatibilidade de saves e riscos de regressão quando aplicável;
- confirmação de que arquivos alheios e dados reais do usuário foram preservados.

Sem branch/hash imutáveis e evidência dos testes, a tarefa não está pronta para revisão do CR.
