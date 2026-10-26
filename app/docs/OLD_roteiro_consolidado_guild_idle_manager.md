# Roteiro Consolidado — Próximas Entregas do Guild Idle Manager

## Base da análise

Foram analisados os dois roteiros enviados:

- `proximas_entregas1.md`: propõe uma evolução mais avançada do gameplay, partindo da premissa de que classes, evolução, taverna, troca de classe e UX medieval já existem.
- `proximas_entregas2.md`: propõe uma evolução mais fundacional, com polimento de UX/UI, balanceamento, consolidação das classes, Taverna 2.0, missões, equipamentos e idle offline.

## Diagnóstico

As evoluções citadas fazem sentido, mas os dois arquivos não devem ser executados como roteiros paralelos.

O segundo roteiro é mais adequado para consolidar a base do jogo antes de expandir o gameplay. Ele trata de UX, balanceamento, progressão, Taverna, missões, equipamentos e idle offline.

O primeiro roteiro é mais adequado como camada posterior de profundidade. Ele adiciona bônus reais de classe, sinergia de grupo, restrições de equipamento, skills, dungeons avançadas, bosses, crafting, refino, progressão de guilda, conquistas e revisão econômica.

A sequência correta não é escolher um ou outro. O caminho mais seguro é unir os dois em uma linha única:

```text
UX estável → balanceamento base → classes úteis → taverna estratégica → missões → equipamentos → skills → conteúdo difícil → crafting/refino → progressão longa → coleção → balanceamento final
```

---

# Roteiro único recomendado

## MVP-012 — Hardening UX/UI e consistência visual

### Objetivo

Consolidar a base visual medieval/fantasia já entregue no MVP-011, corrigindo inconsistências, melhorando legibilidade e preparando a interface para novos sistemas.

### Justificativa

Antes de adicionar sistemas grandes, a interface precisa estar estável. Como o jogo vai receber mais classes, atributos, equipamentos, missões, dungeons e recompensas, a base visual precisa suportar esse crescimento sem ficar confusa.

### Escopo

- Revisar responsividade das telas principais.
- Padronizar botões, cards, headers, menus, ícones e estados visuais.
- Melhorar feedbacks de ação: sucesso, erro, loading e estados vazios.
- Criar placeholders visuais para assets futuros:
  - Avatar de mercenário.
  - Ícone de classe.
  - Ícone de raridade.
  - Ícone de recurso.
  - Imagem de item.
  - Imagem de dungeon.
- Ajustar hierarquia visual entre ações principais e secundárias.
- Melhorar tela inicial/dashboard da guilda.
- Melhorar mensagens vazias, como “Nenhum mercenário contratado ainda”.
- Garantir que todas as telas sigam a identidade medieval/fantasia atual.

### Entrega esperada

Base visual mais consistente, responsiva e preparada para expansão.

---

## MVP-013 — Balanceamento base e configurações centrais

### Objetivo

Revisar os números-base do jogo e centralizar regras de balanceamento para facilitar ajustes futuros.

### Justificativa

Balanceamento precisa vir antes de expandir muito o conteúdo. Se XP, gold, atributos, custos e raridades estiverem quebrados, qualquer sistema novo nasce torto.

### Escopo

- Revisar curva de XP por nível.
- Revisar ganho de gold.
- Revisar crescimento de atributos por nível.
- Revisar impacto de raridade dos mercenários.
- Revisar progressão de classes:
  - Aprendiz.
  - Primeira classe.
  - Especialização.
  - Classe final.
- Criar constantes ou configurações centralizadas para:
  - XP por nível.
  - Gold por fonte.
  - Multiplicadores de raridade.
  - Custos de contratação.
  - Custos de refresh da Taverna.
  - Chance de sucesso em missões.
  - Recompensas.
- Preparar estrutura para ajustes finos sem alterar várias partes do código.

### Entrega esperada

Economia e progressão básica mais controláveis, com regras centralizadas.

---

## MVP-014 — Classes reais, evolução e bônus de gameplay

### Objetivo

Transformar o sistema de classes em uma mecânica real de gameplay, e não apenas uma informação visual.

### Justificativa

O jogo já caminha para ter classes e evolução. O próximo passo é fazer cada classe ter função prática dentro das missões, dungeons e composição do grupo.

### Escopo

- Manter Aprendiz como classe inicial no nível 1.
- Permitir escolha da primeira classe no nível 20:
  - Warrior.
  - Rogue.
  - Mage.
  - Cleric.
  - Archer.
- Criar ou consolidar especialização no nível 100.
- Criar ou consolidar classe final no nível 350.
- Criar tela ou modal de escolha/evolução de classe.
- Exibir requisitos visuais para evolução.
- Impedir evolução caso o mercenário não cumpra os requisitos.
- Exibir classe atual e próximo marco de evolução.
- Aplicar bônus reais por classe.
- Criar bônus individuais por função:
  - Warrior: resistência, defesa ou chance de proteger o grupo.
  - Rogue: crítico, velocidade ou chance de recompensa extra.
  - Mage: dano mágico, dano em área ou bônus contra inimigos especiais.
  - Cleric: cura, redução de falha ou recuperação após missão.
  - Archer: precisão, dano consistente ou bônus contra alvos específicos.
- Criar base inicial para sinergia de grupo:
  - Bônus por composição equilibrada.
  - Penalidade ou menor eficiência em grupos mal distribuídos.
  - Requisitos de classe para conteúdos futuros.

### Entrega esperada

Classes com impacto real no gameplay e base pronta para skills, equipamentos e dungeons avançadas.

---

## MVP-015 — Taverna 2.0 e contratação estratégica

### Objetivo

Transformar a Taverna em uma feature mais estratégica, visual e atrativa para contratação de mercenários.

### Justificativa

A Taverna é uma das features com maior potencial de identidade do jogo. Ela deve virar um ponto recorrente de decisão: contratar agora, esperar, renovar, buscar raridade melhor ou economizar recursos.

### Escopo

- Melhorar a contratação de mercenários.
- Exibir raridade visualmente.
- Exibir atributos antes da contratação.
- Exibir classe ou potencial de classe quando aplicável.
- Adicionar custo de contratação.
- Adicionar limite de opções disponíveis.
- Criar botão de renovar ofertas.
- Criar cooldown ou custo para refresh da Taverna.
- Preparar estrutura para mercenários especiais.
- Melhorar feedback visual ao contratar um mercenário.
- Destacar mercenários raros ou especiais quando aparecerem.
- Preparar base para eventos futuros de contratação.

### Entrega esperada

Taverna mais útil, mais visual e com decisões reais de contratação.

---

## MVP-016 — Missões / Expedições Foundation

### Objetivo

Criar o primeiro loop jogável onde os mercenários são enviados para gerar recompensas.

### Justificativa

O jogo precisa de um loop central além de contratar e evoluir mercenários. Missões/expedições dão utilidade direta para atributos, classes e composição de grupo.

### Escopo

- Criar missões com dificuldade.
- Permitir enviar mercenários para missões.
- Definir tempo de conclusão.
- Criar recompensas:
  - Gold.
  - XP.
  - Materiais futuros.
  - Equipamentos futuros.
- Calcular chance de sucesso com base nos atributos dos mercenários.
- Considerar bônus de classe na chance de sucesso.
- Criar tela de missão em andamento.
- Criar tela de resultado da missão.
- Exibir sucesso, falha e recompensas recebidas.
- Preparar base para missões raras, diárias e eventos futuros.

### Entrega esperada

Primeiro loop funcional de envio de mercenários, recompensa e progressão.

---

## MVP-017 — Equipamentos simples e restrições por classe

### Objetivo

Adicionar uma nova camada de progressão para os mercenários e preparar restrições de equipamentos por classe.

### Justificativa

Equipamentos aumentam profundidade sem exigir ainda um sistema complexo de crafting ou refino. Também ajudam a diferenciar classes e builds.

### Escopo

- Criar equipamentos por slot:
  - Arma.
  - Armadura.
  - Acessório.
- Criar raridade dos equipamentos.
- Criar bônus de atributos por item.
- Permitir drop de equipamentos por missão.
- Permitir equipar e desequipar itens nos mercenários.
- Criar comparação simples entre item atual e novo item.
- Exibir impacto do equipamento nos atributos do mercenário.
- Criar restrições básicas por classe:
  - Warrior: espadas, escudos, armaduras pesadas.
  - Rogue: adagas, couro, acessórios de crítico.
  - Mage: cajados, mantos, itens de INT.
  - Cleric: maças, livros, itens de suporte.
  - Archer: arcos, armaduras leves, itens de precisão.
- Preparar estrutura para equipamentos específicos de especialização/classe final.
- Preparar estrutura para inventário e crafting futuro.

### Entrega esperada

Sistema básico de equipamentos com impacto real e compatibilidade com classes.

---

## MVP-018 — Idle offline / progresso passivo

### Objetivo

Fazer o jogo funcionar melhor como idle, gerando progresso mesmo quando o jogador estiver fora.

### Justificativa

Como o jogo é idle, o progresso offline é uma feature estrutural. Ele reforça o hábito de retorno e dá sensação de continuidade.

### Escopo

- Calcular progresso enquanto o jogador ficou offline.
- Exibir resumo ao retornar ao jogo.
- Gerar gold e XP com base no tempo ausente.
- Considerar mercenários ativos, missões e progresso da guilda.
- Definir limite máximo de tempo offline, como:
  - 8 horas.
  - 12 horas.
  - 24 horas.
- Evitar exploração por alteração de relógio local, se aplicável.
- Exibir claramente o que foi acumulado durante o período offline.
- Preparar base para bônus futuros de produção offline.

### Entrega esperada

Sistema de progresso offline básico, com resumo de retorno e limite configurável.

---

## MVP-019 — Skills Foundation

### Objetivo

Criar a primeira base de habilidades por classe, começando por efeitos simples, passivos ou automáticos.

### Justificativa

Depois que classes, missões e equipamentos estiverem funcionando, skills passam a ter contexto. Antes disso, seriam apenas bônus soltos.

### Escopo

- Criar estrutura de habilidades por classe.
- Começar com habilidades passivas ou automáticas.
- Relacionar skills com classes e especializações.
- Criar efeitos simples, como:
  - Aumentar chance de sucesso.
  - Aumentar XP recebido.
  - Aumentar gold recebido.
  - Reduzir tempo de missão.
  - Aumentar dano ou defesa em dungeons.
  - Melhorar chance de drop.
- Exibir habilidades na tela de detalhe do mercenário.
- Preparar estrutura para evolução de skill no futuro.
- Preparar estrutura para skills ativas em versões futuras.

### Entrega esperada

Base técnica e visual para habilidades por classe.

---

## MVP-020 — Dungeons avançadas e bosses

### Objetivo

Criar conteúdos mais difíceis, com requisitos de composição, classes específicas e chefes.

### Justificativa

Depois que classes, equipamentos e skills existirem, o jogo precisa de desafios que justifiquem essas camadas de progressão.

### Escopo

- Criar dungeons com dificuldade maior.
- Criar bosses.
- Definir requisitos mínimos:
  - Nível.
  - Power Score.
  - Classe.
  - Composição de grupo.
  - Equipamento.
- Criar recompensas melhores para dungeons avançadas.
- Criar chances de drop mais raras.
- Considerar sinergia de grupo no cálculo de sucesso.
- Criar feedback visual para vitória, derrota e recompensas.
- Preparar base para dungeons temporárias ou eventos.

### Entrega esperada

Conteúdo mais desafiador para dar sentido à progressão avançada.

---

## MVP-021 — Crafting / Blacksmith Foundation

### Objetivo

Criar o sistema base de ferreiro/crafting usando materiais obtidos em missões e dungeons.

### Justificativa

Crafting aumenta o valor do farm e cria uma nova forma de progressão controlada.

### Escopo

- Criar estrutura de materiais.
- Permitir obtenção de materiais em missões e dungeons.
- Criar tela de Ferreiro/Blacksmith.
- Criar receitas simples de equipamentos.
- Consumir materiais e gold no crafting.
- Definir raridade do item criado.
- Criar feedback visual de criação.
- Preparar base para receitas raras e exclusivas.

### Entrega esperada

Sistema inicial de crafting com uso real para materiais.

---

## MVP-022 — Upgrade / Refino de equipamentos

### Objetivo

Permitir melhorar equipamentos existentes com custo e progressão incremental.

### Justificativa

Refino dá longevidade ao sistema de equipamentos e cria um novo destino para gold e materiais.

### Escopo

- Permitir upgrade de equipamentos.
- Definir custo por nível de melhoria.
- Consumir gold e/ou materiais.
- Aumentar atributos do item conforme o nível.
- Definir limite de upgrade por raridade.
- Avaliar risco de falha ou progressão garantida.
- Criar feedback visual de sucesso/falha.
- Exibir comparação antes e depois do upgrade.

### Entrega esperada

Sistema inicial de melhoria de equipamentos, aumentando profundidade da progressão.

---

## MVP-023 — Expansão da progressão da guilda

### Objetivo

Expandir a guilda como núcleo de progressão de longo prazo.

### Justificativa

A guilda precisa ser mais do que uma tela central. Ela deve representar evolução permanente, desbloqueios e benefícios acumulados.

### Escopo

- Criar ou expandir nível da guilda.
- Criar construções ou melhorias internas.
- Criar benefícios permanentes.
- Relacionar evolução da guilda com:
  - Limite de mercenários.
  - Qualidade da Taverna.
  - Eficiência de missões.
  - Produção offline.
  - Chance de drop.
  - Desbloqueio de dungeons.
- Criar tela de progresso da guilda.
- Criar custos de melhoria.
- Criar requisitos por nível.

### Entrega esperada

Progressão de longo prazo para dar mais objetivo ao jogo.

---

## MVP-024 — Achievements / Collection / Codex

### Objetivo

Criar conquistas, coleção e registro de progresso do jogador.

### Justificativa

Conquistas e coleção aumentam retenção, dão metas paralelas e valorizam o histórico do jogador.

### Escopo

- Criar sistema de conquistas.
- Criar coleção de mercenários.
- Criar coleção de classes descobertas.
- Criar coleção de equipamentos.
- Criar Codex com registros desbloqueados.
- Criar recompensas simples por conquista.
- Exibir progresso de coleção.
- Preparar base para conquistas secretas ou raras.

### Entrega esperada

Camada de progressão lateral, coleção e histórico.

---

## MVP-025 — Balance Pass e revisão geral de economia

### Objetivo

Revisar todos os números após a entrada dos principais sistemas de gameplay.

### Justificativa

O balanceamento do MVP-013 será base. Este balance pass deve ser mais completo, já considerando classes, taverna, missões, equipamentos, skills, dungeons, crafting, refino, guilda e idle offline.

### Escopo

- Revisar XP.
- Revisar gold.
- Revisar custos de contratação.
- Revisar custos de refresh da Taverna.
- Revisar custos de crafting.
- Revisar custos de upgrade/refino.
- Revisar drops.
- Revisar raridades.
- Revisar dificuldade de missões.
- Revisar dificuldade de dungeons.
- Revisar progressão de guilda.
- Revisar produção offline.
- Revisar power curve dos mercenários.
- Revisar impacto das classes e skills.
- Corrigir gargalos ou progressões rápidas demais.

### Entrega esperada

Economia mais estável e jogo pronto para novas expansões de conteúdo.

---

# Melhorias paralelas recomendadas

Estas melhorias podem entrar junto das MVPs, sem necessariamente virar uma entrega grande separada:

- Adicionar tooltip nos atributos:
  - STR.
  - AGI.
  - INT.
  - VIT.
- Criar tela de detalhes do mercenário.
- Criar log de eventos da guilda.
- Criar filtros na lista de mercenários:
  - Classe.
  - Raridade.
  - Nível.
  - Status.
- Criar ordenação por:
  - Nível.
  - Poder.
  - Raridade.
  - Nome.
- Melhorar feedback visual de level up.
- Criar sistema básico de Power Score do mercenário.
- Preparar enum/tabela de raridades.
- Centralizar textos fixos para facilitar manutenção.
- Melhorar feedbacks visuais de:
  - Contratação.
  - Evolução.
  - Erro.
  - Sucesso.
  - Falha em missão.
  - Drop raro.
- Garantir que todas as novas entregas sigam a UX/UI medieval já implantada.

---

# Ordem final recomendada

```text
MVP-012 — Hardening UX/UI e consistência visual
MVP-013 — Balanceamento base e configurações centrais
MVP-014 — Classes reais, evolução e bônus de gameplay
MVP-015 — Taverna 2.0 e contratação estratégica
MVP-016 — Missões / Expedições Foundation
MVP-017 — Equipamentos simples e restrições por classe
MVP-018 — Idle offline / progresso passivo
MVP-019 — Skills Foundation
MVP-020 — Dungeons avançadas e bosses
MVP-021 — Crafting / Blacksmith Foundation
MVP-022 — Upgrade / Refino de equipamentos
MVP-023 — Expansão da progressão da guilda
MVP-024 — Achievements / Collection / Codex
MVP-025 — Balance Pass e revisão geral de economia
```

---

# Recomendação objetiva

A próxima entrega deve ser o **MVP-012 — Hardening UX/UI e consistência visual**.

Motivo: o MVP-011 já entregou a nova base visual, mas antes de empilhar novas features, vale estabilizar responsividade, padrões visuais, feedbacks, placeholders e legibilidade.

Depois disso, o caminho mais seguro é:

```text
Balancear → consolidar classes → melhorar Taverna → criar missões → adicionar equipamentos → adicionar idle offline → aprofundar gameplay
```

Isso evita crescimento desorganizado e mantém o projeto evoluindo de forma consistente.
