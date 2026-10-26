# Roteiro Consolidado — Próximas Entregas do Guild Idle Manager

## Base da análise

Foram analisados os três arquivos enviados:

- `proximas_entregas1.md`
- `proximas_entregas2.md`
- `melhorias.txt`

O MVP-011 — UX/UI Medieval Redesign já foi considerado como entregue. Portanto, este roteiro parte da premissa de que o jogo já possui uma base visual medieval/fantasia e agora precisa evoluir com mais consistência de gameplay, balanceamento e progressão.

---

## Diagnóstico objetivo

As evoluções citadas fazem sentido, mas não devem ser executadas exatamente na ordem original dos arquivos.

O primeiro arquivo propõe uma evolução mais avançada: bônus de classe, sinergia de grupo, restrição de equipamentos, skills, dungeons avançadas, crafting, refino, progressão de guilda, conquistas e revisão de economia.

O segundo arquivo propõe uma evolução mais segura para a base: polimento visual, balanceamento, evolução real das classes, Taverna 2.0, missões, equipamentos e idle offline.

O terceiro arquivo traz ajustes importantes de produto, principalmente:

- Missões filtradas por construções da guilda e faixas de nível.
- Tela explicativa de classes.
- Nerf na distribuição inicial de atributos dos mercenários.
- Ordenação/filtros em telas com muitos dados.
- Atalho para demitir mercenário.
- Contratação em massa de 10 mercenários.
- Fonte passiva de gold.
- Mercado para venda de itens.
- Acentuação correta.
- Comunicação 100% em Português BR.

A decisão correta é unificar tudo em uma única linha de evolução:

```text
UX estável → localização PT-BR → balanceamento base → classes úteis → Taverna estratégica → missões → equipamentos/inventário → idle offline → mercado → skills → conteúdo difícil → crafting/refino → progressão longa → coleção → balanceamento final
```

---

## Decisões de consolidação

### O que faz sentido manter

Todas as evoluções fazem sentido para o Guild Idle Manager.

O ponto principal é dependência. Algumas features só fazem sentido depois de outras:

- Skills fazem mais sentido depois de classes, missões e equipamentos.
- Dungeons avançadas e bosses fazem mais sentido depois de missões, classes úteis, equipamentos e skills.
- Crafting precisa de materiais, inventário e equipamentos antes.
- Refino precisa de equipamentos já funcionando.
- Mercado precisa de inventário e itens vendáveis antes.
- Balanceamento precisa acontecer cedo e também no final.
- Idle offline precisa existir, mas com ganho controlado para não quebrar a economia.

### O que precisa mudar na ordem

A ordem do primeiro arquivo é boa para profundidade futura, mas começa avançada demais.

A ordem do segundo arquivo é melhor como base, mas precisa absorver os ajustes do terceiro arquivo, principalmente localização, acentuação, nerf de atributos, filtros, mercado e contratação em massa.

---

# Roteiro único recomendado

## MVP-012 — Hardening UX/UI, localização PT-BR e consistência visual

### Objetivo

Consolidar a base visual medieval/fantasia entregue no MVP-011, corrigindo inconsistências, melhorando legibilidade e garantindo que o sistema esteja 100% em Português BR.

### Justificativa

Antes de adicionar sistemas grandes, a interface precisa estar estável. O jogo vai receber mais classes, atributos, equipamentos, missões, inventário, mercado, dungeons e recompensas. Se a base visual e textual não estiver padronizada agora, a complexidade vai crescer desorganizada.

### Escopo

- Revisar responsividade das telas principais.
- Padronizar botões, cards, headers, menus, ícones e estados visuais.
- Melhorar feedbacks de ação:
  - Sucesso.
  - Erro.
  - Carregamento.
  - Estados vazios.
- Criar placeholders visuais para assets futuros:
  - Avatar de mercenário.
  - Ícone de classe.
  - Ícone de raridade.
  - Ícone de recurso.
  - Imagem de item.
  - Imagem de dungeon.
- Melhorar tela inicial/dashboard da guilda.
- Melhorar mensagens vazias, como:
  - “Nenhum mercenário contratado ainda.”
  - “Nenhuma missão disponível.”
  - “Nenhum item encontrado.”
- Garantir acentuação correta em todas as telas.
- Garantir comunicação 100% em Português BR.
- Remover textos em inglês da interface, como:
  - `common`
  - `uncommon`
  - `available`
  - `fail`
  - `success`
- Criar camada centralizada de textos/labels para facilitar manutenção.
- Manter enums internos em inglês, se fizer sentido tecnicamente, mas sempre traduzir na camada visual.
- Criar padrão de tradução visual para raridades:
  - Comum.
  - Incomum.
  - Raro.
  - Épico.
  - Lendário.
- Criar padrão de tradução visual para classes:
  - Aprendiz.
  - Guerreiro.
  - Ladino.
  - Mago.
  - Clérigo.
  - Arqueiro.
- Adicionar tooltips nos atributos:
  - FOR.
  - AGI.
  - INT.
  - VIT.
  - Outros atributos existentes.
- Melhorar tela/lista de mercenários:
  - Botão `Detalhes`.
  - Botão `Demitir` direto na listagem.
  - Manter a opção de demissão também dentro dos detalhes do mercenário.
- Criar ordenação na lista de mercenários por:
  - Poder Total.
  - Nível.
  - Raridade.
  - Nome.
  - FOR.
  - AGI.
  - INT.
  - VIT.
- Melhorar feedback visual de level up.
- Melhorar feedback visual de contratação, evolução, erro, sucesso e falha.

### Entrega esperada

Sistema visualmente mais consistente, legível, responsivo e pronto para expansão. A interface deve estar em Português BR, com acentuação correta e sem termos soltos em inglês.

---

## MVP-013 — Balanceamento base, RNG de atributos e configurações centrais

### Objetivo

Revisar os números-base do jogo e centralizar regras de balanceamento para facilitar ajustes futuros.

### Justificativa

O balanceamento precisa vir antes da expansão de conteúdo. Se XP, gold, atributos, raridades e custos estiverem descontrolados, Taverna, missões, equipamentos, idle e mercado já nascerão quebrados.

### Escopo

- Revisar curva de XP por nível.
- Revisar ganho de gold.
- Revisar crescimento de atributos por nível.
- Revisar impacto da raridade dos mercenários.
- Revisar custo de contratação.
- Revisar custo de renovação da Taverna.
- Revisar progressão de classes:
  - Aprendiz.
  - Primeira classe.
  - Especialização.
  - Classe final.
- Criar constantes/configurações centralizadas para:
  - XP por nível.
  - Gold por fonte.
  - Custo de contratação.
  - Custo de renovação da Taverna.
  - Multiplicadores de raridade.
  - Distribuição inicial de atributos.
  - Cálculo de Poder Total.
  - Chance de sucesso em missões.
  - Recompensas.
- Nerfar levemente a distribuição inicial de atributos dos mercenários.
- Ajustar geração de mercenários comuns para evitar muitos personagens nível 1 com Poder Total acima de 20.
- Diretriz inicial sugerida:
  - Mercenário comum: Poder Total médio mais baixo, com teto aproximado próximo de 15.
  - Mercenário incomum: pode ultrapassar 20, mas com teto aproximado próximo de 25.
  - Raridades superiores: podem ter tetos maiores, mas com chance mais controlada.
- Garantir que o RNG continue interessante, mas sem banalizar mercenários fortes.
- Criar ou consolidar cálculo de Poder Total do mercenário.
- Preparar estrutura para ajustes finos sem alterar várias partes do código.

### Entrega esperada

Economia, progressão e geração de mercenários mais controladas. O jogo fica menos quebrável e mais fácil de balancear nas próximas entregas.

---

## MVP-014 — Classes reais, evolução e guia de classes

### Objetivo

Transformar o sistema de classes em uma mecânica real de gameplay, com progressão clara, bônus úteis e uma tela explicativa para orientar o jogador.

### Justificativa

Como os mercenários possuem atributos com RNG, o jogador precisa entender quais atributos combinam com cada classe. Sem isso, a decisão de investir ou demitir um mercenário fica cega.

### Escopo

- Manter Aprendiz como classe inicial no nível 1.
- Permitir escolha da primeira classe no nível 20:
  - Guerreiro.
  - Ladino.
  - Mago.
  - Clérigo.
  - Arqueiro.
- Criar ou consolidar especialização no nível 100.
- Criar ou consolidar classe final no nível 350.
- Criar tela/modal de escolha e evolução de classe.
- Exibir requisitos visuais para evolução.
- Impedir evolução caso o mercenário não cumpra os requisitos.
- Exibir classe atual e próximo marco de evolução.
- Aplicar bônus reais por classe.
- Criar bônus individuais por função:
  - Guerreiro: resistência, defesa ou proteção do grupo.
  - Ladino: crítico, velocidade ou chance de recompensa extra.
  - Mago: dano mágico, dano em área ou bônus contra inimigos especiais.
  - Clérigo: cura, redução de falha ou recuperação após missão.
  - Arqueiro: precisão, dano consistente ou bônus contra alvos específicos.
- Criar base inicial para sinergia de grupo:
  - Bônus por composição equilibrada.
  - Penalidade ou menor eficiência em grupos mal distribuídos.
  - Requisitos de classe para conteúdos futuros.
- Criar tela de informações sobre classes.
- A tela de classes deve exibir:
  - Descrição de cada classe.
  - Melhores atributos para cada classe.
  - Caminho de progressão.
  - Marcos de nível.
  - Bônus recebidos por classe.
  - Quais atributos aumentam conforme a evolução.
  - Sugestão de perfil ideal do mercenário.
- Conectar essa tela com a decisão de manter, evoluir ou demitir mercenários.

### Entrega esperada

Classes com impacto real no gameplay e uma tela de orientação para o jogador tomar decisões melhores sobre seus mercenários.

---

## MVP-015 — Taverna 2.0 e contratação estratégica

### Objetivo

Transformar a Taverna em uma feature mais estratégica, visual e atrativa para contratação de mercenários.

### Justificativa

A Taverna deve ser um dos principais pontos de decisão do jogo. O jogador precisa avaliar custo, atributos, raridade, potencial e risco antes de contratar.

### Escopo

- Melhorar a contratação de mercenários.
- Exibir raridade visualmente.
- Exibir atributos antes da contratação.
- Exibir Poder Total antes da contratação.
- Exibir custo de contratação.
- Adicionar limite de opções disponíveis na Taverna.
- Criar botão de renovar ofertas.
- Criar cooldown ou custo para renovar ofertas.
- Preparar estrutura para mercenários especiais.
- Melhorar feedback visual ao contratar um mercenário.
- Destacar mercenários raros ou especiais quando aparecerem.
- Criar confirmação antes de contratações relevantes.
- Criar contratação em massa de 10 mercenários.
- Na contratação em massa:
  - Calcular o custo total considerando a regra atual de escala como se fossem 10 contratações individuais.
  - Exibir popup de confirmação com o custo total.
  - Validar se o jogador possui gold suficiente.
  - Gerar os 10 mercenários após confirmação.
  - Gerar nomes automaticamente.
- Para geração de nomes:
  - Usar inicialmente uma lista local/base simples de nomes.
  - Permitir expansão futura para tabela de nomes por cultura, raridade ou origem.
  - Evitar nomes duplicados em sequência quando possível.
- Indicar que contratação em massa é uma mecânica mais útil para late game.

### Entrega esperada

Taverna mais estratégica, visual e escalável, com suporte tanto para contratação individual quanto para contratação em massa.

---

## MVP-016 — Missões / Expedições Foundation

### Objetivo

Criar o primeiro loop jogável em que mercenários são enviados para missões e retornam com recompensas.

### Justificativa

O jogo precisa de um loop central além de contratar e evoluir mercenários. Missões dão utilidade para atributos, classes, Poder Total e composição de grupo.

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
- Considerar Poder Total na chance de sucesso.
- Criar tela de missão em andamento.
- Criar tela de resultado da missão.
- Exibir sucesso, falha e recompensas recebidas.
- Exibir apenas missões disponíveis para a guilda de acordo com construções/desbloqueios.
- Separar missões por submenus de faixa de nível:
  - 1–20.
  - 21–50.
  - 51–100.
  - 101–130.
  - 131–200.
  - 200+.
- Impedir envio para missão caso os requisitos não sejam cumpridos.
- Preparar base para missões raras, diárias e eventos futuros.

### Entrega esperada

Primeiro loop funcional de missão, recompensa e progressão, já preparado para crescer com guilda, classes e dungeons.

---

## MVP-017 — Equipamentos simples, inventário e restrições por classe

### Objetivo

Adicionar uma camada de progressão por equipamentos e organizar a base de inventário.

### Justificativa

Equipamentos aumentam profundidade sem exigir ainda crafting ou refino. Inventário e filtros são necessários antes de mercado, crafting e dungeons avançadas.

### Escopo

- Criar raridade dos equipamentos.
- Criar bônus de atributos por item.
- Permitir drop de equipamentos por missão.
- Permitir equipar e desequipar itens nos mercenários.
- Criar comparação simples entre item atual e novo item.
- Exibir impacto do equipamento nos atributos do mercenário.
- Criar restrições básicas por classe:
  - Guerreiro: espadas, escudos e armaduras pesadas.
  - Ladino: adagas, couro e acessórios de crítico.
  - Mago: cajados, mantos e itens de INT.
  - Clérigo: maças, livros e itens de suporte.
  - Arqueiro: arcos, armaduras leves e itens de precisão.
- Preparar estrutura para equipamentos específicos de especialização e classe final.
- Criar tela/lista de inventário.
- Criar filtros no inventário por:
  - Todos.
  - Materiais.
  - Armas.
  - Armaduras/peitorais.
  - Acessórios.
  - Raridade.
  - Nível/tier.
- Garantir que o inventário use nomes e descrições em Português BR.
- Preparar estrutura para crafting, mercado e refino.

### Entrega esperada

Sistema básico de equipamentos e inventário, com filtros, restrições por classe e impacto real nos mercenários.

---

## MVP-018 — Idle offline e fonte passiva de gold

### Objetivo

Fazer o jogo funcionar melhor como idle, gerando progresso controlado quando o jogador estiver fora.

### Justificativa

Como o jogo é idle, precisa existir alguma progressão offline. Essa fonte não deve ser lucrativa demais, mas precisa dar sensação de continuidade.

### Escopo

- Calcular progresso enquanto o jogador ficou offline.
- Exibir resumo ao retornar ao jogo.
- Gerar gold passivo de forma controlada.
- Considerar mercenários ativos, nível da guilda ou construções futuras.
- Definir limite máximo de tempo offline, como:
  - 8 horas.
- Evitar exploração por alteração de relógio local, se aplicável.
- Exibir claramente:
  - Tempo ausente.
  - Gold acumulado.
  - Limite aplicado.
- Preparar base para bônus futuros de produção offline por construção da guilda.

### Entrega esperada

Sistema idle offline básico, com gold passivo limitado e resumo claro ao retorno do jogador.

---

## MVP-019 — Mercado e venda de itens

### Objetivo

Criar um sistema de Mercado para vender itens e gerar gold de forma controlada, usando uma construção da guilda como base de progressão.

### Justificativa

Com inventário, materiais e equipamentos, o jogo precisa de uma forma de descarte útil. O Mercado cria um sink de itens, gera gold, dá XP para a guilda e adiciona progressão por slots.

### Escopo

- Criar construção `Mercado`.
- Permitir vender itens pelo Mercado.
- Criar slots de venda.
- Aumentar quantidade de slots conforme evolução da construção.
- Cada item deve ter tempo de venda baseado na raridade/tier.
- Exemplo inicial:
  - Item comum: venda rápida.
  - Item incomum: venda média.
  - Item raro: venda mais lenta.
  - Item épico/lendário: venda longa.
- O tempo deve escalar pela quantidade vendida.
- Exemplo:
  - Madeira comum leva 10 segundos por unidade.
  - 10 madeiras comuns levam 100 segundos.
- Ao colocar item à venda:
  - Remover ou reservar item do inventário.
  - Exibir tempo restante.
  - Exibir valor estimado de venda.
  - Permitir coletar gold ao concluir.
- Cada venda concluída deve gerar pequena XP para a guilda.
- Diretriz inicial:
  - 1 ou 2 XP de guilda por venda concluída.
  - XP por venda, não por quantidade de itens.
- Preparar base para upgrades do Mercado:
  - Mais slots.
  - Redução leve de tempo.
  - Pequeno bônus de valor.
- Garantir que o Mercado não vire a fonte principal de gold antes da hora.

### Entrega esperada

Sistema inicial de venda de itens, com slots, tempo por raridade, coleta de gold e XP leve para a guilda.

---

## MVP-020 — Skills Foundation

### Objetivo

Criar a primeira base de habilidades por classe, começando por efeitos simples, passivos ou automáticos.

### Justificativa

Skills passam a ter contexto depois que classes, missões e equipamentos já existem. Antes disso, seriam apenas bônus soltos.

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
- Exibir habilidades na tela de detalhes do mercenário.
- Preparar estrutura para evolução de skill no futuro.

### Entrega esperada

Base técnica e visual para habilidades por classe.

---

## MVP-021 — Dungeons avançadas e bosses

### Objetivo

Criar conteúdos mais difíceis, com requisitos de composição, classes específicas e chefes.

### Justificativa

Depois que classes, equipamentos, missões e skills existirem, o jogo precisa de desafios que justifiquem essas camadas de progressão.

### Escopo

- Criar dungeons com dificuldade maior.
- Criar bosses.
- Definir requisitos mínimos:
  - Nível.
  - Poder Total.
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

## MVP-022 — Crafting / Ferreiro Foundation

### Objetivo

Criar o sistema base de Ferreiro usando materiais obtidos em missões, mercado e dungeons.

### Justificativa

Crafting aumenta o valor do farm e cria uma forma de progressão mais controlada do que depender apenas de RNG.

### Escopo

- Criar estrutura de materiais.
- Permitir obtenção de materiais em missões e dungeons.
- Criar tela de Ferreiro.
- Criar receitas simples de equipamentos.
- Consumir materiais e gold no crafting.
- Definir raridade do item criado.
- Criar feedback visual de criação.
- Preparar base para receitas raras e exclusivas.
- Integrar crafting com inventário.
- Integrar crafting com Mercado quando fizer sentido.

### Entrega esperada

Sistema inicial de crafting com uso real para materiais.

---

## MVP-023 — Upgrade / Refino de equipamentos

### Objetivo

Permitir melhorar equipamentos existentes com custo e progressão incremental.

### Justificativa

Refino dá longevidade ao sistema de equipamentos e cria um novo destino para gold e materiais.

### Escopo

- Permitir upgrade/refino de equipamentos.
- Definir custo por nível de melhoria.
- Consumir gold e/ou materiais.
- Aumentar atributos do item conforme o nível.
- Definir limite de upgrade por raridade.
- Avaliar risco de falha ou progressão garantida.
- Criar feedback visual de sucesso/falha.
- Exibir comparação antes e depois do upgrade.
- Garantir que refino não substitua completamente a busca por novos equipamentos.

### Entrega esperada

Sistema inicial de melhoria de equipamentos, aumentando profundidade da progressão.

---

## MVP-024 — Expansão da progressão da guilda e construções

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
  - Slots do Mercado.
- Criar tela de progresso da guilda.
- Criar custos de melhoria.
- Criar requisitos por nível.
- Integrar construções com disponibilidade de missões.
- Integrar construções com Mercado e idle offline.

### Entrega esperada

Progressão de longo prazo para dar mais objetivo ao jogo e conectar os sistemas principais.

---

## MVP-025 — Conquistas, Coleção e Codex

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

Camada de progressão lateral, coleção e histórico do jogador.

---

## MVP-026 — Balance Pass e revisão geral de economia

### Objetivo

Revisar todos os números após a entrada dos principais sistemas de gameplay.

### Justificativa

O balanceamento do MVP-013 é preventivo. Este balance pass deve ser mais completo, já considerando classes, Taverna, missões, equipamentos, idle offline, Mercado, skills, dungeons, crafting, refino e progressão da guilda.

### Escopo

- Revisar XP.
- Revisar gold.
- Revisar custos de contratação.
- Revisar custos de renovação da Taverna.
- Revisar custos de crafting.
- Revisar custos de upgrade/refino.
- Revisar valores de venda no Mercado.
- Revisar tempo de venda por raridade/tier.
- Revisar produção offline.
- Revisar drops.
- Revisar raridades.
- Revisar dificuldade de missões.
- Revisar dificuldade de dungeons.
- Revisar progressão da guilda.
- Revisar Power Curve/Poder Total dos mercenários.
- Revisar impacto das classes e skills.
- Corrigir gargalos ou progressões rápidas demais.
- Corrigir fontes de gold excessivas.
- Corrigir recompensas irrelevantes.

### Entrega esperada

Economia mais estável e jogo pronto para novas expansões de conteúdo.

---

# Melhorias encaixadas no roteiro

| Melhoria citada | Onde entra |
|---|---|
| Missões disponíveis por construção e submenus por nível | MVP-016 e MVP-024 |
| Tela explicativa de classes e melhores atributos | MVP-014 |
| Nerf na distribuição inicial de atributos | MVP-013 |
| Ordenação de mercenários e filtros de inventário | MVP-012 e MVP-017 |
| Atalho para demitir mercenário | MVP-012 |
| Contratar 10 mercenários de uma vez | MVP-015 |
| Fonte passiva de gold | MVP-018 |
| Mercado para vender itens | MVP-019 |
| Acentuação correta | MVP-012 |
| Sistema inteiro em Português BR | MVP-012 |

---

# Ordem final recomendada

```text
MVP-012 — Hardening UX/UI, localização PT-BR e consistência visual
MVP-013 — Balanceamento base, RNG de atributos e configurações centrais
MVP-014 — Classes reais, evolução e guia de classes
MVP-015 — Taverna 2.0 e contratação estratégica
MVP-016 — Missões / Expedições Foundation
MVP-017 — Equipamentos simples, inventário e restrições por classe
MVP-018 — Idle offline e fonte passiva de gold
MVP-019 — Mercado e venda de itens
MVP-020 — Skills Foundation
MVP-021 — Dungeons avançadas e bosses
MVP-022 — Crafting / Ferreiro Foundation
MVP-023 — Upgrade / Refino de equipamentos
MVP-024 — Expansão da progressão da guilda e construções
MVP-025 — Conquistas, Coleção e Codex
MVP-026 — Balance Pass e revisão geral de economia
```

---

# Recomendação objetiva

A próxima entrega deve ser:

```text
MVP-012 — Hardening UX/UI, localização PT-BR e consistência visual
```

Motivo: o MVP-011 já entregou a nova base visual, mas antes de empilhar novas features, vale estabilizar responsividade, padrões visuais, feedbacks, acentuação, traduções e legibilidade.

Depois disso, o caminho mais seguro é:

```text
Balancear → consolidar classes → melhorar Taverna → criar missões → adicionar equipamentos/inventário → criar idle offline → criar Mercado → aprofundar gameplay
```

Esse roteiro evita crescimento desorganizado, reduz retrabalho e mantém o projeto evoluindo com uma fundação mais limpa.
