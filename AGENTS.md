# Guild Idle Manager - Fluxo de Desenvolvimento

Este arquivo define o fluxo de trabalho dos agentes DEV, DA e CR no projeto.
O checkout de implementação fica em `C:\Users\vitor\Guild Idle Manager\App GIM`.

## Papéis

- **Conversa principal:** representa o usuário, define escopo, coordena etapas, acompanha evidências e decide quando uma entrega está pronta para validação do usuário.
- **DEV:** implementa as tarefas autorizadas, escreve e executa testes, atualiza documentação de status e cria commits pequenos e rastreáveis.
- **DA (Direção de Arte):** define linguagem visual, componentes, assets e critérios de interface. Não muda regras de negócio nem implementa runtime, salvo autorização explícita.
- **CR (Code Reviewer):** revisa de forma independente um commit/branch já entregue pelo DEV, priorizando bugs, regressões, segurança, integridade de dados e critérios da tarefa. Não altera código durante a revisão.

## Fluxo obrigatório de cada entrega

Este projeto segue o fluxo local deste arquivo. Não há `.pipeline/project.adapter.yaml` configurado neste checkout; essa ausência já foi verificada durante o pacote atual. Não procurar, gerar nem repetir a execução de um verificador que dependa desse adapter a cada item. Usar os testes reais do projeto e registrar a limitação uma vez no handoff. Uma esteira de outro projeto não substitui estes critérios locais.

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

## Guia do Jogo e documentação exportável

- O Guia do Jogo é documentação de gameplay mantida junto ao produto. Sempre que uma entrega alterar uma regra, conteúdo, requisito, recompensa, chance ou fluxo explicado ao jogador, o DEV deve revisar o Guia e atualizá-lo na mesma entrega quando necessário; se não houver impacto, deve registrar isso na evidência da tarefa.
- O Guia exibido no jogo e o arquivo Markdown exportável devem ter uma única fonte de conteúdo. Ao implementar a exportação, preferir gerar o `.md` a partir da mesma fonte usada para renderizar o Guia, incluindo conteúdo dinâmico aplicável (por exemplo, catálogo e taxas ativos) quando isso fizer parte da documentação. Não manter uma cópia manual independente que possa ficar defasada.
- Se a arquitetura exigir um Markdown canônico em vez de geração dinâmica, a tela do Guia e o arquivo exportado devem consumir esse mesmo arquivo, e toda alteração do Guia deve atualizá-lo no mesmo commit.
- O arquivo exportado deve ser PT-BR, legível fora do jogo, conter versão/data de geração e somente informações destinadas ao jogador; nunca incluir dados privados de campanha, saves, credenciais ou conteúdo administrativo interno.
- O handoff ao CR deve comprovar que o conteúdo visível no Guia e o `.md` exportado estão sincronizados, que a exportação representa a versão/conteúdo atual e que alterações de gameplay relevantes foram avaliadas quanto à necessidade de atualizar a documentação.

## Catálogo e busca do Guia

- O catálogo de Equipamentos e Materiais deve continuar derivado das fontes ativas da campanha e compartilhar a mesma estrutura com a tela e a exportação Markdown. Não trate ingredientes consumidos como fontes de obtenção, não invente chances e preserve os requisitos que limitam cada atividade.
- Ao alterar os filtros, normalização de nomes, fontes ou exportação, mantenha testes de paridade API/HTML/Markdown e verifique que nenhuma resposta ou arquivo exportado contenha IDs, estoques ou progresso privados da guilda.

## Campanhas existentes e decisões de coordenação

- Diretriz do usuário: saves antigos não são prioridade de balanceamento econômico. Nunca corromper ou impedir a abertura de uma campanha existente, e permitir que funcionalidades novas sejam iniciadas nela para o usuário testar. Não exigir campanha nova por conveniência de implementação.
- Não criar migrações, compensações, conversões ou regras econômicas complexas apenas para igualar campanhas antigas às novas. Um rebalanceamento pode valer somente para campanhas novas se preservar a integridade e o acesso funcional das existentes; documentar o alcance no handoff e no Guia quando relevante.
- Regras de compatibilidade explicitamente aprovadas para uma entrega continuam válidas. Não apagar trabalho ou dados nem retirar garantias específicas sem evidência de necessidade e decisão de coordenação.
- Quando o usuário delegar decisões de produto à conversa principal, o DEV encaminha dúvidas de regra a ela primeiro e continua o trabalho independente. Não abrir perguntas ao usuário apenas para repetir uma decisão já delegada. Aprovações de segurança, permissões reais e escolhas pessoais indispensáveis continuam com o usuário; se uma ferramenta aguardar resposta humana obrigatória, informar o bloqueio concreto.

## Autorização específica de auditoria visual - 2026-11-24

- Para ML-053 no pacote `feature/anomalies-ui-audit`, o usuário autorizou a DA a abrir o jogo instalado e navegar no save real por toda a plataforma. Essa exceção autoriza somente navegação e observação visual, não testes de mutação ou edição do save. A atualização temporal normal causada pelo próprio jogo deve ser distinguida de ações iniciadas pelo agente.
- Não iniciar/coletar atividades, gastar, recrutar, equipar, resetar, restaurar/importar campanha ou alterar o relógio no save real. Estados que exijam ações devem ser inspecionados em perfis sintéticos ou cópias descartáveis autorizadas, sem modificar o original.
- Coordenar um único operador de interface por vez; manter capturas privadas locais e registrar a cobertura sem publicar dados do save. Consolidar a auditoria em no máximo dois lotes implementáveis na mesma branch; a coordenação aprova o escopo antes da execução pelo DEV.

## Ambiente local de validação

- No checkout `App GIM`, o Python de testes conhecido fica em `..\.venv\Scripts\python.exe`. Este ambiente pode não ter `cryptography`; isso não exige alterar o produto ou instalar pacotes globalmente.
- O pacote atual já validou uma allowlist temporária em `..\scratch\ml052-smoke-allowlist-20261124`, contendo somente `cryptography`, `cffi` e `_cffi_backend` provenientes do runtime confiável. Se essa pasta ainda existir, reutilizá-la via `PYTHONPATH` e propagar a configuração aos subprocessos. Não colocar todo outro `site-packages` à frente do ambiente, simular criptografia ou incluir a allowlist na distribuição/Git.
- Variáveis definidas em uma chamada de terminal não persistem necessariamente na seguinte. Cada execução afetada deve definir seu ambiente explicitamente e registrar a configuração no handoff, sem repetir a investigação de dependências já documentadas. Se a pasta temporária não existir, conferir o runtime antes de presumir um bloqueio ou recriar dependências.
- Usar `TEMP`, `TMP` e perfis de aplicação descartáveis fora de `App GIM`, por exemplo sob `..\scratch`; os guardas de logs/exportação podem rejeitar corretamente arquivos privados dentro do repositório. Nunca remover esses guardas para fazer teste passar, nem apontar o teste para o perfil real do usuário.
- A evidência deve identificar o SHA e as fontes efetivamente testadas. Teste que consome arquivos dirty não comprova isoladamente o commit; falta de dependência, timeout ou suíte interrompida não equivale a aprovação.
