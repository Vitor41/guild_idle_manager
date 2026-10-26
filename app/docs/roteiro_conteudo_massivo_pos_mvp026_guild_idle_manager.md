# Guild Idle Manager — Roteiro de Conteúdo Massivo Pós-MVP-026

## Contexto

A última entrega concluída foi:

```text
MVP-026 — Balance Pass e revisão geral de economia
```

O sistema está funcional e balanceado o suficiente para receber uma grande massa de conteúdo.

Este documento não tem como objetivo recriar mecânicas já existentes. O objetivo é orientar o Codex a criar e popular o banco com conteúdo jogável em grande volume, cobrindo materiais, itens, armas, missões, missões de coleta, profissões simples, dungeons, mercado de docas e tutorial inicial.

Quando este documento usar a expressão “criar conteúdo”, deve ser interpretado como:

```text
Criar massa de dados jogável, seedar/popular o banco de dados e conectar esse conteúdo às mecânicas já existentes.
```

Não deve ser interpretado como recriar a mecânica base, exceto onde explicitamente indicado, como no caso de Docas, mercantes rotativos, profissões simples e tutorial, caso essas estruturas ainda não existam.

---

# Objetivo macro

Criar conteúdo suficiente para o jogador progredir do nível 1 até o nível 350 sem se sentir travado por falta de opções.

O jogador pode eventualmente ficar travado por:

- Falta de gold.
- Falta de power.
- Falta de composição.
- Falta de equipamento.
- Falta de materiais.
- Falta de entendimento do sistema.
- Dificuldade natural de progressão.

Mas não pode ficar travado por falta de conteúdo disponível.

A diretriz principal é:

```text
Não economizar conteúdo.
Gerar milhares de registros.
Cobrir todas as faixas de nível.
Evitar buracos de progressão.
Garantir alternativas de farm.
Garantir explicação mínima para o jogador entender como evoluir.
```

---

# Regras gerais para o Codex

## Autonomia autorizada

O Codex está autorizado a criar conteúdo original em grande escala, incluindo:

- Materiais.
- Armas.
- Armaduras.
- Acessórios.
- Itens especiais.
- Itens de crafting.
- Itens de dungeon.
- Itens de coleta.
- Missões comuns.
- Missões raras.
- Missões de coleta.
- Dungeons.
- Bosses.
- Mercantes das Docas.
- Ofertas de mercantes.
- Textos de tutorial.
- Descrições curtas de lore.
- Slugs/chaves internas.
- Drop tables.
- Pools de recompensa.
- Variações por nível, raridade, bioma e tipo de conteúdo.

Não é necessário pedir nova confirmação para criar variações, desde que respeite as regras deste documento.

## Regra de conteúdo original

Todo conteúdo criado deve ser original.

Evitar nomes protegidos ou diretamente copiados de animes, jogos, filmes, livros, franquias comerciais ou marcas reais.

Pode usar inspiração genérica de fantasia medieval, como:

- Bosques antigos.
- Minas abandonadas.
- Catacumbas.
- Ruínas.
- Fortalezas.
- Portais.
- Mercadores.
- Ferreiros.
- Bestas.
- Cultistas.
- Guardiões.
- Relíquias.

Não usar nomes como “Goku”, “Naruto”, “Kenshin”, “Pikachu”, “Agumon”, etc. em itens, missões, dungeons, bosses ou mercantes.

## Português BR obrigatório

Todo texto exibido ao usuário deve estar em Português BR.

Obrigatório revisar:

- Acentuação.
- Plural.
- Gênero.
- Labels.
- Mensagens de erro.
- Estados vazios.
- Nomes de raridade.
- Nomes de tipo de item.
- Nomes de missão.
- Descrições.
- Recompensas.
- Tutorial.

Não pode aparecer em tela:

```text
common
uncommon
rare
available
fail
success
weapon
armor
material
quest
dungeon
merchant
```

A camada técnica pode manter enums em inglês, se o projeto já usa esse padrão, mas a camada visual precisa traduzir tudo.

## Seed idempotente

Todo conteúdo deve ser criado via seed/migration/script idempotente.

Regras obrigatórias:

- Não duplicar registros ao rodar o seed mais de uma vez.
- Usar `slug`, `code`, `external_key` ou campo equivalente como identificador único.
- Não apagar dados do usuário.
- Não truncar tabelas com dados transacionais.
- Usar upsert/update seguro para conteúdo base.
- Versionar seeds por pacote de conteúdo.
- Registrar origem do conteúdo quando possível, por exemplo:
  - `content_pack = "mvp_027_content_foundation"`
  - `content_pack = "mvp_028_items_materials"`
  - `content_pack = "mvp_029_missions_1_350"`

Se o projeto já possuir padrão de seed, seguir o padrão existente. Se não possuir, criar uma estrutura clara em `app/seeds`, `scripts`, `database/seeds` ou diretório equivalente do projeto.

## Não quebrar mecânicas existentes

Antes de criar novas tabelas, verificar se já existem modelos/tabelas equivalentes.

A prioridade deve ser:

```text
1. Reutilizar tabelas e serviços existentes.
2. Expandir campos apenas se necessário.
3. Criar novas tabelas somente quando o conteúdo exigir.
4. Não remover comportamento já funcional.
```

## Escala mínima esperada

A meta é criar milhares de conteúdos somando todos os pacotes.

Diretriz mínima:

| Tipo de conteúdo | Quantidade mínima recomendada |
|---|---:|
| Materiais | 300+ |
| Equipamentos | 1.500+ |
| Missões comuns | 1.000+ |
| Missões de coleta | 500+ |
| Dungeons/variações de dungeon | 300+ |
| Bosses/variações de chefe | 100+ |
| Mercantes/modelos de mercante | 80+ |
| Ofertas/pools de Docas | 1.000+ |
| Páginas/etapas de tutorial | 10+ |
| Profissões | 8 a 12 |

Esses números são mínimos. Se for tecnicamente viável, gerar mais.

---

# Faixas de progressão

Todo conteúdo deve respeitar faixas de progressão.

Usar como referência principal:

| Tier | Faixa de nível | Papel no jogo |
|---|---:|---|
| T1 | 1–20 | Introdução, Aprendiz, farm básico |
| T2 | 21–50 | Primeira classe, equipamentos simples |
| T3 | 51–100 | Consolidação, início de especialização |
| T4 | 101–130 | Pós-especialização inicial |
| T5 | 131–200 | Mid game estruturado |
| T6 | 201–250 | Mid/late game |
| T7 | 251–300 | Late game |
| T8 | 301–350 | End game atual |

Evitar buracos de conteúdo.

Para cada faixa de nível deve existir:

- Missões comuns.
- Missões de coleta.
- Dungeons.
- Materiais relevantes.
- Equipamentos relevantes.
- Recompensas compatíveis.
- Opções de compra nas Docas.
- Pelo menos alguns itens raros e épicos.
- Pelo menos um conjunto de desafios mais difíceis.

---

# Raridades

Usar as raridades já existentes no sistema. Se o sistema ainda não tiver raridade consolidada, usar a seguinte estrutura visual:

| Ordem | Raridade | Uso |
|---:|---|---|
| 1 | Comum | Conteúdo base, farm frequente |
| 2 | Incomum | Melhorias leves |
| 3 | Raro | Drops desejáveis |
| 4 | Épico | Conteúdo difícil ou caro |
| 5 | Lendário | Drops raros e alto custo |
| 6 | Mítico | Opcional, somente se o sistema já suportar ou se for seguro criar |

Não criar raridades novas se isso quebrar enums, telas, filtros ou balanceamento.

## Pesos gerais de raridade

Para drops e ofertas comuns:

| Raridade | Peso inicial sugerido |
|---|---:|
| Comum | 60% |
| Incomum | 25% |
| Raro | 10% |
| Épico | 4% |
| Lendário | 1% |

Para dungeons difíceis, bosses e Docas evoluídas, esses pesos podem melhorar gradualmente.

---

# MVP-027 — Fundação de conteúdo e infraestrutura de seed

## Objetivo

Criar a base técnica para gerar, versionar, validar e popular conteúdo em massa sem duplicação e sem risco para dados do usuário.

## Escopo

- Mapear as tabelas existentes de:
  - Itens.
  - Materiais.
  - Equipamentos.
  - Missões.
  - Dungeons.
  - Drop tables.
  - Recompensas.
  - Construções.
  - Mercenários.
  - Profissões, se já existir.
- Criar estrutura de seeds idempotentes.
- Criar helpers reutilizáveis para:
  - Criar slugs.
  - Normalizar acentos quando necessário para chave técnica.
  - Garantir nomes visuais com acento.
  - Criar faixas de nível.
  - Criar raridades.
  - Criar rewards.
  - Criar drop pools.
  - Validar duplicidade.
- Criar validador de conteúdo.
- Criar relatório pós-seed informando:
  - Quantidade de materiais criados.
  - Quantidade de equipamentos criados.
  - Quantidade de missões criadas.
  - Quantidade de dungeons criadas.
  - Quantidade de mercantes criados.
  - Quantidade de ofertas criadas.
  - Erros ou registros ignorados.
- Garantir que todos os seeds possam ser rodados em ambiente local.

## Regras de negócio

- Seed deve ser seguro para rodar várias vezes.
- Conteúdo base deve ser marcado como ativo.
- Conteúdo removido futuramente deve ser desativado, não apagado.
- Não pode sobrescrever dados de progresso do usuário.
- Não pode resetar inventário, missões em andamento ou mercenários.
- Toda chave técnica deve ser estável.

## Critérios de aceite

- Executar seed completo sem duplicar dados.
- Rodar seed duas vezes e manter as mesmas quantidades finais.
- Exibir relatório de criação/atualização.
- Garantir que todos os conteúdos tenham nome em Português BR.
- Garantir que todos os conteúdos tenham faixa de nível ou regra de disponibilidade.
- Garantir que todo conteúdo tenha raridade válida quando aplicável.
- Garantir que não existam slugs duplicados.

---

# MVP-028 — Catálogo massivo de materiais, itens e equipamentos

## Objetivo

Criar grande volume de materiais, itens e equipamentos para sustentar farm, missões, dungeons, crafting, mercado e progressão até o nível 350.

## Diretriz principal

O jogo precisa ter variedade suficiente para que o jogador veja progresso e recompensa com frequência.

Criar conteúdo em volume, usando combinações de:

- Tipo.
- Tier.
- Raridade.
- Bioma.
- Origem.
- Prefixo.
- Sufixo.
- Classe favorecida.
- Atributo favorecido.
- Faixa de nível.

## Categorias de materiais

Criar materiais em pelo menos estas famílias:

| Família | Exemplos de uso |
|---|---|
| Madeiras | Crafting de arcos, cajados, escudos, estruturas |
| Minérios | Crafting de armas, armaduras e refino |
| Pedras | Construções, refino, runas |
| Couros | Armaduras leves, acessórios |
| Tecidos/Fibras | Mantôs, túnicas, acessórios mágicos |
| Ervas | Consumíveis futuros, alquimia, missões |
| Essências | Crafting mágico, skills, refino |
| Gemas | Acessórios, encantamentos, itens raros |
| Ossos/Presas/Garras | Armas, troféus, crafting raro |
| Relíquias/Fragmentos | Dungeons, codex, crafting especial |
| Catalisadores | Refino, upgrade, crafting avançado |
| Insígnias | Recompensas de dungeons e bosses |

## Materiais por tier

Criar variações por tier.

Exemplos de famílias e evolução:

### Madeiras

| Tier | Exemplos de nomes |
|---|---|
| T1 | Madeira Bruta, Galho Seco, Tábua Simples |
| T2 | Madeira de Carvalho, Tora Resistente, Fibra de Raiz |
| T3 | Madeira Sombria, Casca Antiga, Tábua Reforçada |
| T4 | Madeira de Cedro Arcano, Raiz Profunda, Lenho Polido |
| T5 | Madeira de Árvore Anciã, Casca Rúnica, Viga Encantada |
| T6 | Lenho de Bosque Esquecido, Madeira Lunar, Raiz Cristalizada |

### Minérios

| Tier | Exemplos de nomes |
|---|---|
| T1 | Minério de Cobre, Pedra de Ferro, Cascalho Metálico |
| T2 | Minério de Ferro, Veio de Estanho, Fragmento de Prata |
| T3 | Minério de Aço Negro, Prata Bruta, Pedra Magnética |
| T4 | Minério de Mithril, Ouro Impuro, Cristal de Forja |
| T5 | Adamantita Bruta, Prata Lunar, Ferro Rúnico |
| T6 | Oricalco, Aço Estelar, Veio Abissal |

### Ervas

| Tier | Exemplos de nomes |
|---|---|
| T1 | Erva Verde, Folha Curativa, Musgo Macio |
| T2 | Flor Azul, Raiz Amarga, Broto Silvestre |
| T3 | Erva Sombria, Cogumelo Rubro, Folha Prateada |
| T4 | Flor Lunar, Raiz Arcana, Espinho Dourado |
| T5 | Erva Ancestral, Pétala Rúnica, Seiva Viva |
| T6 | Flor do Eclipse, Raiz de Mana, Musgo Cristalino |

## Quantidade mínima de materiais

Criar no mínimo:

| Família | Quantidade mínima |
|---|---:|
| Madeiras | 40 |
| Minérios | 50 |
| Pedras | 30 |
| Couros | 35 |
| Tecidos/Fibras | 35 |
| Ervas | 45 |
| Essências | 40 |
| Gemas | 35 |
| Ossos/Presas/Garras | 35 |
| Relíquias/Fragmentos | 40 |
| Catalisadores | 30 |
| Insígnias | 20 |

Total mínimo esperado: 435 materiais.

## Equipamentos

Criar equipamentos para os slots existentes no sistema.

Se o sistema atualmente suportar apenas:

- Arma.
- Armadura.
- Acessório.

Usar apenas esses slots.

Se o sistema já suportar mais slots, pode expandir respeitando o padrão existente.

## Armas por classe/função

Criar armas compatíveis com as classes existentes:

| Classe/função | Tipos de armas |
|---|---|
| Guerreiro | Espada, Machado, Martelo, Lança |
| Ladino | Adaga, Lâmina Curta, Rapieira |
| Mago | Cajado, Varinha, Grimório |
| Clérigo | Maça, Cetro, Livro Sagrado |
| Arqueiro | Arco, Besta, Lança Leve |
| Uso geral | Espada curta, Bastão, Punhal, Arco simples |

## Armaduras

Criar armaduras com variações:

| Tipo | Perfil |
|---|---|
| Couro leve | AGI, esquiva, ladinos e arqueiros |
| Malha | equilíbrio entre defesa e mobilidade |
| Placas | VIT, defesa, guerreiros |
| Túnica | INT, mana, magos e clérigos |
| Manto | suporte, resistência mágica |

## Acessórios

Criar acessórios com bônus variados:

- Anéis.
- Amuletos.
- Medalhões.
- Braceletes.
- Talismãs.
- Broches.
- Insígnias.
- Pingentes.

## Atributos favorecidos

Usar atributos existentes no sistema. Se existirem os atributos abaixo, seguir a lógica:

| Atributo | Uso |
|---|---|
| FOR | Dano físico, Guerreiro, Ladino parcial, Arqueiro parcial |
| AGI | Velocidade, crítico, esquiva, Ladino, Arqueiro |
| INT | Magia, cura, suporte, Mago, Clérigo |
| VIT | Vida, defesa, resistência, Guerreiro, Clérigo parcial |

## Geração massiva por prefixo e sufixo

Para gerar grande volume sem criar tudo manualmente, usar combinação de:

### Prefixos por raridade

| Raridade | Prefixos exemplo |
|---|---|
| Comum | Simples, Gasto, Rústico, Básico, Antigo |
| Incomum | Reforçado, Polido, Leve, Resistente, Afiado |
| Raro | Sombrio, Flamejante, Congelante, Rúnico, Dourado |
| Épico | Ancestral, Abissal, Celestial, Dracônico, Sagrado |
| Lendário | Primordial, Eterno, Divino, Imperial, Estelar |

### Sufixos por atributo

| Atributo | Sufixos exemplo |
|---|---|
| FOR | do Impacto, da Força, do Destruidor, da Guerra |
| AGI | da Agilidade, das Sombras, do Vento, da Precisão |
| INT | da Sabedoria, do Arcano, da Chama, da Lua |
| VIT | da Vitalidade, da Guarda, da Fortaleza, do Guardião |

Exemplos de nomes gerados:

- Espada Reforçada da Força.
- Cajado Rúnico do Arcano.
- Arco Leve da Precisão.
- Armadura de Placas Ancestral da Fortaleza.
- Anel Celestial da Sabedoria.
- Adaga Sombria das Sombras.

## Quantidade mínima de equipamentos

Gerar no mínimo:

| Categoria | Quantidade mínima |
|---|---:|
| Armas | 700 |
| Armaduras | 500 |
| Acessórios | 500 |

Total mínimo esperado: 1.700 equipamentos.

## Regras de distribuição por nível

Para cada faixa T1 a T6, deve existir:

- Armas comuns.
- Armas incomuns.
- Pelo menos algumas armas raras.
- Armaduras comuns.
- Armaduras incomuns.
- Pelo menos algumas armaduras raras.
- Acessórios comuns.
- Acessórios incomuns.
- Pelo menos alguns acessórios raros.
- Itens épicos, lendários e míticos em menor volume, de preferencia, sendo possivel o drop nos conteudos avançados do game.

## Critérios de aceite

- Criar pelo menos 400 materiais.
- Criar pelo menos 1.500 equipamentos.
- Garantir distribuição entre nível 1 e 350.
- Garantir que cada classe tenha armas adequadas em todas as faixas de nível.
- Garantir que cada faixa de nível tenha materiais úteis.
- Garantir que todos os itens tenham nome, descrição, raridade, tipo e faixa de nível.
- Garantir que todos os itens possam aparecer em drops, missões, dungeons, Docas ou crafting futuro.
- Garantir que o seed rode sem duplicar dados.

---

# MVP-029 — Conteúdo massivo de missões do nível 1 ao 350

## Objetivo

Criar missões suficientes para o jogador sempre ter alternativas de progressão, farm de gold, farm de XP, farm de itens e progressão de mercenários. DELETAR missões que já existam cadastradas e criar as novas.

## Tipos de missão

Criar missões em múltiplos tipos:

| Tipo | Descrição |
|---|---|
| Combate | Derrotar inimigos, limpar rotas, enfrentar ameaças |
| Patrulha | Missões de risco baixo/médio com XP consistente |
| Escolta | Recompensa maior em gold, risco moderado |
| Caçada | Foco em partes de criaturas, couro, presas e garras |
| Exploração | Foco em relíquias, gemas, fragmentos e descoberta |
| Investigação | Foco em XP e itens raros ocasionais |
| Defesa | Proteger caravanas, vilas, portões ou construções |
| Resgate | Risco maior, boa recompensa |
| Contrato | Missões com recompensa direta de gold |
| Elite | Missões difíceis, exigem power maior |
| Rara | Aparecimento limitado ou recompensa superior |
| História leve | Pequenos textos de ambientação, sem complexidade excessiva |

## Campos esperados por missão

Cada missão deve ter, conforme o modelo do projeto permitir:

- `slug` ou `code`.
- Nome.
- Descrição curta.
- Tipo.
- Tier.
- Nível mínimo.
- Nível máximo ou nível recomendado.
- Dificuldade.
- Tempo de duração.
- Power recomendado.
- Quantidade mínima de mercenários.
- Quantidade máxima de mercenários.
- Classes recomendadas.
- Construção necessária, se aplicável.
- Gold mínimo/máximo.
- XP mínimo/máximo.
- Drop table.
- Chance base de sucesso.
- Tags.
- Ativa/inativa.
- Pacote de conteúdo.

## Dificuldades

Usar dificuldades visuais em Português BR.

| Dificuldade | Uso |
|---|---|
| Muito fácil | Tutorial, início do jogo |
| Fácil | Farm seguro |
| Normal | Progressão padrão |
| Difícil | Requer time razoável |
| Perigosa | Risco alto, recompensa melhor |
| Heróica | Conteúdo avançado |
| Lendária | Conteúdo raro/end game |

A camada técnica pode usar enum em inglês, se já existir, mas a interface deve mostrar Português BR.

## Distribuição mínima por faixa

Criar no mínimo:

| Faixa | Missões comuns | Missões raras/elite | Total mínimo |
|---|---:|---:|---:|
| 1–20 | 120 | 20 | 140 |
| 21–50 | 140 | 30 | 170 |
| 51–100 | 180 | 40 | 220 |
| 101–130 | 120 | 30 | 150 |
| 131–200 | 220 | 60 | 280 |
| 201–250 | 180 | 50 | 230 |
| 251–300 | 180 | 50 | 230 |
| 301–350 | 180 | 60 | 240 |

Total mínimo esperado: 1.660 missões.

Pode gerar mais se o padrão de seed permitir.

## Regras de recompensa

Recompensas devem respeitar o balanceamento do MVP-026.

Não hardcodar números se já existirem constantes de economia.

Diretriz:

- Missões fáceis devem dar menos gold e XP, porém com boa taxa de sucesso.
- Missões normais devem ser o caminho padrão de progressão.
- Missões difíceis devem ter recompensa melhor, mas risco maior.
- Missões raras/elite devem ter chance melhor de item raro.
- Missões de nível mais alto devem escalar recompensa, tempo e power recomendado.

## Regras de disponibilidade

Missões devem ser filtradas por:

- Nível da guilda.
- Construções desbloqueadas.
- Faixa de nível.
- Requisitos de power.
- Requisitos de classe, quando aplicável.
- Disponibilidade ativa.

A tela deve evitar mostrar conteúdo impossível cedo demais, salvo se já existir uma UX clara de “bloqueado”.

## Submenus de missões

Separar missões por faixas:

- 1–20.
- 21–50.
- 51–100.
- 101–130.
- 131–200.
- 201–250.
- 251–300.
- 301–350.

Se a UI já usa outra segmentação, adaptar mantendo as mesmas faixas lógicas.

## Exemplos de missões por tier

### T1 — 1 a 20

- Patrulha na Estrada da Guilda.
- Caçada aos Lobos Famintos.
- Escolta ao Ferreiro Local.
- Busca por Madeira Bruta.
- Limpeza do Depósito Abandonado.
- Defesa da Carroça de Suprimentos.
- Investigação no Celeiro Quebrado.
- Contrato contra Saqueadores Iniciantes.

### T2 — 21 a 50

- Patrulha na Floresta Baixa.
- Caçada ao Urso Cinzento.
- Escolta até a Vila do Rio.
- Incursão na Mina Velha.
- Defesa da Ponte de Pedra.
- Resgate no Acampamento de Bandidos.
- Investigação das Ruínas Úmidas.
- Contrato da Guarda Mercante.

### T3 — 51 a 100

- Exploração do Bosque Sombrio.
- Caçada ao Basilisco Jovem.
- Defesa da Torre de Vigia.
- Escolta da Caravana do Norte.
- Investigação dos Cristais Partidos.
- Limpeza da Cripta Menor.
- Contrato contra Cultistas.
- Patrulha no Vale das Cinzas.

### T4 — 101 a 130

- Incursão na Fortaleza Quebrada.
- Caçada à Mantícora Ferida.
- Defesa dos Portões Antigos.
- Investigação do Santuário Rúnico.
- Contrato dos Nobres da Fronteira.
- Resgate na Caverna de Vidro.
- Exploração do Caminho Submerso.
- Patrulha no Desfiladeiro do Eco.

### T5 — 131 a 200

- Ataque ao Forte Escarlate.
- Defesa da Rota dos Mercadores.
- Caçada ao Wyvern das Colinas.
- Exploração das Catacumbas Fundas.
- Resgate no Templo Esquecido.
- Investigação do Obelisco Sombrio.
- Contrato contra Capitães Renegados.
- Patrulha na Estrada do Pântano.

### T6 — 201 a 250

- Incursão no Santuário Abissal.
- Caçada ao Golem de Obsidiana.
- Defesa da Torre Lunar.
- Escolta do Arquimago Viajante.
- Exploração das Minas Dracônicas.
- Investigação do Portal Instável.
- Contrato da Coroa Partida.
- Resgate nas Ruínas Suspensas.

### T7 — 251 a 300

- Guerra contra a Legião Sombria.
- Caçada ao Dragão Menor.
- Defesa do Bastião Celestial.
- Exploração do Labirinto Estelar.
- Investigação da Fenda Arcana.
- Resgate no Forte Sem Nome.
- Contrato dos Sete Selos.
- Patrulha no Caminho do Vazio.

### T8 — 301 a 350

- Cerco à Fortaleza Primordial.
- Caçada ao Dragão Ancião.
- Defesa da Guilda contra o Arauto.
- Exploração do Portal do Vazio.
- Investigação do Trono Esquecido.
- Resgate no Plano Fragmentado.
- Contrato contra o Senhor das Cinzas.
- Patrulha na Fronteira Celestial.

## Critérios de aceite

- Criar pelo menos 1.500 missões.
- Cobrir todas as faixas de nível até 350.
- Garantir que cada faixa tenha missões de gold, XP, item e progressão.
- Garantir que missões usem drops reais cadastrados no MVP-028.
- Garantir que missões respeitem construções/desbloqueios quando aplicável.
- Garantir que missões apareçam no menu correto por faixa.
- Garantir textos em Português BR.
- Garantir seed idempotente.

---

# MVP-030 — Missões de coleta e profissões simples

## Objetivo

Criar missões específicas para coleta de materiais e um sistema simples de profissões para bonificar esse tipo de missão.

## Diretriz principal

Profissões não devem virar um sistema complexo neste momento.

A função é simples:

```text
Alguns mercenários possuem uma profissão.
Essa profissão concede bônus em missões específicas de coleta.
```

## Profissões recomendadas

Criar de 8 a 12 profissões.

| Profissão | Bônus principal |
|---|---|
| Lenhador | Bônus em coleta de madeiras |
| Minerador | Bônus em coleta de minérios |
| Herborista | Bônus em coleta de ervas |
| Coureiro | Bônus em coleta de couros, peles e partes de criaturas |
| Tecelão | Bônus em fibras, tecidos e mantos |
| Garimpeiro | Bônus em gemas e cristais |
| Relicário | Bônus em relíquias e fragmentos antigos |
| Alquimista | Bônus em essências e catalisadores |
| Rastreador | Bônus em caçadas e coleta selvagem |
| Comerciante | Pequeno bônus em venda/compra nas Docas, se tecnicamente simples |

Se o sistema ficar mais simples com apenas 8 profissões, priorizar:

- Lenhador.
- Minerador.
- Herborista.
- Coureiro.
- Tecelão.
- Garimpeiro.
- Relicário.
- Alquimista.

## Regra de atribuição de profissão

Se não existir profissão ainda:

- Cada mercenário pode ter no máximo 1 profissão.
- Profissão pode ser definida em uma missão "simples" dentro do conteudo de troca de classe, custará ouro e um tempo de treinamento para o mercenario se especializar naquilo.
- Profissão pode ser exibida na tela do mercenário.
- Profissão não precisa ter level próprio neste momento.
- Profissão não precisa ter árvore de evolução.
- Profissão não deve afetar combate diretamente.
- Profissão deve afetar somente missões de coleta ou sistemas relacionados.

## Bônus sugerido

Bônus simples por profissão:

| Compatibilidade | Bônus sugerido |
|---|---:|
| Profissão compatível com a missão | +10% a +20% na quantidade coletada |
| Profissão parcialmente compatível | +5% |
| Profissão não compatível | sem bônus |

Se existir raridade de mercenário, pode aplicar bônus adicional pequeno:

| Raridade do mercenário | Bônus adicional |
|---|---:|
| Comum | +0% |
| Incomum | +2% |
| Raro | +4% |
| Épico | +6% |
| Lendário | +8% |
| Mítico | +10% |

Evitar bônus exagerado para não quebrar economia.

## Missões de coleta

Criar missões específicas por tipo de material:

| Tipo de coleta | Exemplos |
|---|---|
| Madeira | Corte no Bosque Baixo, Extração de Lenho Antigo |
| Minério | Escavação de Cobre, Mineração de Mithril |
| Ervas | Colheita de Ervas Verdes, Busca pela Flor Lunar |
| Couro/partes | Rastreamento de Feras, Coleta de Presas |
| Tecidos/fibras | Coleta de Fibras Silvestres, Tear do Vale |
| Gemas | Garimpo no Rio Claro, Extração de Cristais |
| Relíquias | Busca em Ruínas, Fragmentos do Santuário |
| Essências | Coleta de Mana, Extração de Essência Sombria |

## Quantidade mínima de missões de coleta

Criar no mínimo:

| Faixa | Missões de coleta mínimas |
|---|---:|
| 1–20 | 60 |
| 21–50 | 70 |
| 51–100 | 80 |
| 101–130 | 60 |
| 131–200 | 90 |
| 201–250 | 70 |
| 251–300 | 70 |
| 301–350 | 70 |

Total mínimo esperado: 570 missões de coleta.

## Regras de coleta

- Missões de coleta devem ter risco menor que missões de combate.
- Missões de coleta devem dar menos XP de combate.
- Missões de coleta devem ser uma fonte confiável de materiais.
- Algumas missões de coleta podem ter chance baixa de item raro.
- Profissão compatível deve melhorar o resultado.
- Coleta deve complementar Docas, não substituir completamente.
- Coleta deve ser organizada por faixa de nível.

## Exemplos de missões de coleta

### Madeira

- Coleta de Galhos Secos.
- Corte de Madeira Bruta.
- Extração de Carvalho Antigo.
- Busca por Casca Rúnica.
- Lenho do Bosque Esquecido.
- Raiz do Mundo.

### Minério

- Escavação de Cobre.
- Veio de Ferro.
- Mineração de Prata Bruta.
- Extração de Mithril.
- Busca por Oricalco.
- Núcleo de Metal Primordial.

### Ervas

- Colheita de Ervas Verdes.
- Busca por Raiz Amarga.
- Jardim de Folhas Prateadas.
- Flor Lunar.
- Pétala Celestial.
- Orvalho Eterno.

### Relíquias

- Fragmentos da Capela Velha.
- Insígnias de Soldados Antigos.
- Cacos de Obelisco.
- Relíquia do Santuário Rúnico.
- Fragmento do Trono Esquecido.

## Critérios de aceite

- Criar pelo menos 8 profissões.
- Criar pelo menos 500 missões de coleta.
- Cada profissão deve ter pelo menos uma família de material compatível.
- Cada faixa de nível deve ter missões de coleta.
- Missões de coleta devem dropar materiais reais do catálogo.
- Profissão deve ser exibida no mercenário.
- Bônus de profissão deve ser aplicado apenas em contexto compatível.
- Textos devem estar em Português BR.
- Seed deve ser idempotente.

---

# MVP-031 — Conteúdo massivo de dungeons até o nível 350

## Objetivo

Criar uma quantidade relevante de dungeons, dificuldades, bosses e recompensas para dar profundidade à progressão até o nível 350.

## Diretriz principal

Dungeons são conteúdo de desafio.

Devem exigir:

- Power maior.
- Composição melhor.
- Equipamentos melhores.
- Classes úteis.
- Tempo maior.
- Risco maior.

Em troca, devem oferecer:

- XP melhor.
- Gold melhor.
- Drops melhores.
- Materiais raros.
- Itens exclusivos.
- Insígnias.
- Recompensas de boss.

## Estrutura recomendada

Cada dungeon base pode gerar variações.

Exemplo:

```text
Mina Velha
Mina Velha — Difícil
Mina Velha — Heróica
Mina Velha — Profunda
Mina Velha — Chefe
```

Isso permite criar grande volume sem depender de nomes totalmente manuais.

## Biomas/temas de dungeon

Criar dungeons usando estes temas:

| Tema | Uso |
|---|---|
| Minas | Minérios, gemas, golems, feras subterrâneas |
| Bosques | Madeiras, ervas, criaturas selvagens |
| Catacumbas | Ossos, relíquias, mortos-vivos |
| Ruínas | Fragmentos, inscrições, relíquias |
| Fortalezas | Armas, armaduras, gold, inimigos humanos |
| Torres | Essências, grimórios, itens mágicos |
| Cavernas | Couros, cristais, minérios |
| Pântanos | Ervas, venenos, criaturas |
| Santuários | itens sagrados, clérigos, relíquias |
| Portais | essências raras, conteúdo late game |
| Abismos | itens sombrios, bosses fortes |
| Cidades perdidas | conteúdo end game, relíquias e lendários |

## Quantidade mínima por faixa

Criar no mínimo:

| Faixa | Dungeons base | Variações/dificuldades | Total mínimo |
|---|---:|---:|---:|
| 1–20 | 12 | 3 por base | 36 |
| 21–50 | 16 | 3 por base | 48 |
| 51–100 | 24 | 3 por base | 72 |
| 101–130 | 16 | 3 por base | 48 |
| 131–200 | 28 | 3 por base | 84 |
| 201–250 | 24 | 3 por base | 72 |
| 251–300 | 24 | 3 por base | 72 |
| 301–350 | 28 | 3 por base | 84 |

Total mínimo esperado: 516 variações de dungeons.

## Bosses

Criar bosses para parte das dungeons.

Mínimo:

| Faixa | Bosses mínimos |
|---|---:|
| 1–20 | 5 |
| 21–50 | 8 |
| 51–100 | 12 |
| 101–130 | 8 |
| 131–200 | 15 |
| 201–250 | 12 |
| 251–300 | 12 |
| 301–350 | 15 |

Total mínimo esperado: 87 bosses.

Pode arredondar para 100+ bosses.

## Regras de dungeon

- Dungeon deve ter nível mínimo.
- Dungeon deve ter power recomendado.
- Dungeon deve ter tempo de conclusão maior que missão comum.
- Dungeon deve ter chance de falha mais relevante.
- Dungeon deve ter drop table própria.
- Dungeon pode exigir construção da guilda.
- Dungeon pode exigir composição ou classe recomendada.
- Dungeon pode ter boss final.
- Dungeon pode ter tentativas limitadas ou cooldown, se a mecânica existir.
- Dungeon não deve ser a melhor fonte de todos os recursos.
- Dungeon deve ser a melhor fonte de drops raros e itens especiais.

## Dificuldades de dungeon

| Dificuldade | Comportamento |
|---|---|
| Normal | Entrada da dungeon |
| Difícil | Recompensa melhor, risco maior |
| Heróica | Requer time forte |
| Lendária | Conteúdo de end game/raridade alta |

Não criar dificuldade além do que a UI suporta. Se a UI suportar apenas níveis simples, mapear internamente.

## Exemplos de dungeons

### T1

- Porão dos Ratos Cinzentos.
- Mina Baixa Abandonada.
- Bosque dos Galhos Secos.
- Cripta dos Aprendizes.
- Covil dos Saqueadores.

### T2

- Mina Velha do Norte.
- Ruínas da Ponte Quebrada.
- Caverna das Presas.
- Torre do Vigia Caído.
- Bosque da Névoa Baixa.

### T3

- Catacumbas da Lua Fraca.
- Fortaleza dos Renegados.
- Santuário das Ervas Prateadas.
- Mina de Aço Negro.
- Vale das Sombras Curtas.

### T4

- Fortaleza Quebrada.
- Caverna de Vidro.
- Templo do Sino Mudo.
- Torre da Chama Azul.
- Cripta do Guardião Sem Rosto.

### T5

- Catacumbas Fundas.
- Fortaleza Escarlate.
- Bosque da Árvore Anciã.
- Ruínas do Obelisco Sombrio.
- Mina da Adamantita Bruta.

### T6

- Santuário Abissal.
- Minas Dracônicas.
- Torre Lunar.
- Portal Instável.
- Cidade Suspensa em Ruínas.

### T7

- Labirinto Estelar.
- Bastião Celestial.
- Forte Sem Nome.
- Fenda Arcana.
- Covil do Dragão Menor.

### T8

- Fortaleza Primordial.
- Portal do Vazio.
- Trono Esquecido.
- Abismo Celestial.
- Covil do Dragão Ancião.

## Critérios de aceite

- Criar pelo menos 300 variações de dungeons.
- Preferencialmente criar 500+ variações.
- Criar pelo menos 80 bosses.
- Preferencialmente criar 100+ bosses.
- Cobrir todas as faixas até 350.
- Integrar drops com materiais e equipamentos reais.
- Garantir que dungeons tenham requisitos coerentes.
- Garantir que dungeons não quebrem a economia.
- Garantir nomes e descrições em Português BR.
- Seed deve ser idempotente.

---

# MVP-032 — Docas da Guilda e mercantes rotativos

## Objetivo

Criar o menu/construção de Docas da Guilda, onde mercantes rotativos oferecem materiais, itens e equipamentos para venda em intervalos de tempo.

## Conceito

As Docas são uma construção da guilda.

De tempos em tempos, mercantes passam pelas Docas oferecendo produtos.

O foco principal é venda de materiais para o jogador, criando:

- Alternativa ao farm por missão.
- Dreno de gold.
- Sensação de mundo vivo.
- Rotação de oportunidades.
- Progressão da construção Docas.

## Regras principais

- O jogador pode comprar materiais nas Docas.
- O foco das Docas deve ser materiais.
- Equipamentos podem aparecer, mas com menor frequência.
- Itens raros podem aparecer, mas com chance baixa.
- Conforme a construção Docas evolui:
  - Aumentam os slots de produtos.
  - Aumenta a chance de mercantes melhores.
  - Aumenta a chance de itens de maior raridade.
  - Pode reduzir levemente o tempo de rotação.
- Tudo que existe como item no jogo pode passar pelas Docas, mas com peso diferente.
- Materiais devem ser a maior parte das ofertas.

## Construção: Docas

Criar construção chamada:

```text
Docas
```

Descrição sugerida:

```text
Ponto de chegada de mercantes, barqueiros e caravanas marítimas. Quanto mais desenvolvidas forem as Docas, melhores serão os produtos oferecidos à guilda.
```

## Progressão da construção Docas

Sugestão inicial:

| Nível das Docas | Slots de oferta | Chance de Raro+ | Tempo de rotação |
|---:|---:|---:|---:|
| 1 | 4 | 2% | 6h |
| 2 | 5 | 3% | 6h |
| 3 | 6 | 4% | 5h |
| 4 | 7 | 5% | 5h |
| 5 | 8 | 7% | 4h |
| 6 | 9 | 9% | 4h |
| 7 | 10 | 11% | 3h |
| 8 | 11 | 13% | 3h |
| 9 | 12 | 16% | 3h |
| 10 | 14 | 20% | 2h |

Se o sistema de construções já usa outra progressão, adaptar mantendo o conceito.

## Tipos de mercantes

Criar pelo menos 80 modelos de mercantes.

Famílias de mercantes:

| Tipo de mercante | Foco |
|---|---|
| Mercador de Madeiras | Madeiras e fibras |
| Mercador de Minérios | Minérios, pedras e metais |
| Herborista Viajante | Ervas e essências naturais |
| Garimpeiro do Rio | Gemas e cristais |
| Curtidor de Peles | Couros, peles, presas e garras |
| Tecelão Itinerante | Tecidos, mantos e fibras |
| Relicário Errante | Relíquias e fragmentos |
| Alquimista de Porto | Catalisadores e essências |
| Ferreiro de Caravana | Armas e materiais de forja |
| Armeiro Naval | Armaduras e escudos |
| Colecionador Raro | Itens raros com preço alto |
| Contrabandista | Produtos raros, caros e instáveis |
| Emissário de Guilda | Insígnias e itens especiais |

## Pool de ofertas

Criar pelo menos 1.000 possíveis ofertas/pools de Docas.

Distribuição sugerida:

| Categoria | Peso |
|---|---:|
| Materiais comuns/incomuns | 65% |
| Materiais raros | 15% |
| Equipamentos comuns/incomuns | 10% |
| Equipamentos raros | 5% |
| Catalisadores/relíquias | 4% |
| Lendários/especiais | 1% |

Docas de nível alto podem melhorar os pesos.

## Regras de preço

As Docas são dreno de gold.

Preço deve ser:

- Maior do que o valor esperado de venda do item.
- Alto o suficiente para não substituir completamente o farm.
- Útil para completar materiais faltantes.
- Progressivamente mais caro conforme tier e raridade.
- Mais caro para itens raros, épicos e lendários.

Regra relativa sugerida:

```text
preço_doca = valor_base_item * multiplicador_raridade * multiplicador_tier * multiplicador_conveniência
```

Onde `multiplicador_conveniência` deve deixar o item comprado mais caro do que obtido via farm.

## Estoque

Cada oferta deve ter estoque limitado.

Diretriz:

| Raridade | Estoque sugerido |
|---|---:|
| Comum | 10–100 unidades |
| Incomum | 5–50 unidades |
| Raro | 1–20 unidades |
| Épico | 1–5 unidades |
| Lendário | 1 unidade |

Equipamentos normalmente devem ter estoque 1.

Materiais podem ter estoque maior.

## Rotação

- Rotação deve ser controlada pelo servidor/banco.
- Não depender apenas do relógio do frontend.
- Salvar data/hora da próxima rotação.
- Ao expirar, gerar nova rotação.
- Evitar reroll infinito gratuito.
- Se existir botão de renovar, cobrar gold ou item.
- Registrar ofertas ativas para o jogador.

## Interface

Criar menu:

```text
Docas
```

Dentro dele, exibir:

- Nível atual das Docas.
- Tempo restante para próxima rotação.
- Mercantes ativos.
- Slots disponíveis.
- Produtos por mercante.
- Nome do item.
- Tipo.
- Raridade.
- Quantidade em estoque.
- Preço unitário.
- Preço total.
- Botão comprar.
- Feedback de compra.
- Mensagem de gold insuficiente.
- Indicação de raridade.
- Informação de melhoria da construção.

## Critérios de aceite

- Criar construção Docas.
- Criar tela/menu de Docas.
- Criar rotação de mercantes.
- Criar pelo menos 80 modelos de mercantes.
- Criar pelo menos 1.000 ofertas possíveis.
- Garantir que materiais sejam o foco das Docas.
- Garantir que equipamentos apareçam com menor frequência.
- Garantir que raridades altas sejam mais prováveis em Docas evoluídas.
- Garantir que compra consuma gold.
- Garantir que estoque seja respeitado.
- Garantir que rotação não dependa apenas do frontend.
- Garantir textos em Português BR.

---

# MVP-033 — Tutorial inicial para novos usuários

## Objetivo

Criar um tutorial básico para novos usuários entenderem como iniciar, contratar mercenários, fazer missões, farmar materiais, usar equipamentos, evoluir a guilda e acessar Docas.

## Comportamento esperado

Ao primeiro acesso do usuário, exibir um popup perguntando:

```text
Deseja participar de um tutorial rápido para conhecer o jogo?
```

Opções:

```text
Sim, iniciar tutorial
Não, pular tutorial
```

## Regras de persistência

Se o usuário clicar em “Sim”:

- Iniciar tutorial.
- Guiar por páginas/etapas.
- Ao concluir, salvar no banco que o tutorial foi concluído.
- Não perguntar novamente no próximo login.

Se o usuário clicar em “Não”:

- Salvar no banco que o tutorial foi recusado.
- Não perguntar novamente no próximo login.

Criar campo/tabela conforme padrão do sistema:

Opção simples:

```text
users.tutorial_status
```

Valores:

- `pending`
- `completed`
- `declined`

Ou usar campos booleanos:

```text
tutorial_completed
tutorial_declined
```

Priorizar o padrão já existente no projeto.

## Reabrir tutorial

Se for simples, criar opção no menu:

```text
Ajuda / Ver tutorial novamente
```

Essa opção não deve resetar o status automaticamente, apenas permitir assistir de novo.

## Etapas recomendadas do tutorial

Criar pelo menos 10 páginas/etapas.

### Etapa 1 — Boas-vindas

Texto sugerido:

```text
Bem-vindo ao Guild Idle Manager. Aqui você administra uma guilda, contrata mercenários, envia grupos em missões, coleta materiais, conquista equipamentos e evolui sua estrutura ao longo do tempo.
```

### Etapa 2 — Guilda

Explicar:

- A guilda é o centro da progressão.
- Construções desbloqueiam recursos.
- Evoluir a guilda libera mais possibilidades.

### Etapa 3 — Taverna

Explicar:

- Mercenários são contratados na Taverna.
- Cada mercenário possui atributos, raridade e potencial.
- Nem todo mercenário será bom para tudo.

### Etapa 4 — Atributos

Explicar:

- FOR ajuda em dano físico.
- AGI ajuda em velocidade, precisão ou esquiva.
- INT ajuda em magia, cura ou suporte.
- VIT ajuda em resistência e sobrevivência.

Adaptar aos atributos reais do sistema.

### Etapa 5 — Classes

Explicar:

- Mercenários começam como Aprendiz.
- No nível correto, podem evoluir de classe.
- Cada classe aproveita melhor alguns atributos.
- Consultar o guia de classes ajuda a decidir em quem investir.

### Etapa 6 — Missões

Explicar:

- Missões geram XP, gold, itens e materiais.
- Missões têm dificuldade e requisitos.
- Grupos mais fortes têm mais chance de sucesso.

### Etapa 7 — Missões de coleta

Explicar:

- Missões de coleta são voltadas para materiais.
- Algumas profissões melhoram o resultado.
- Use coleta quando precisar de madeira, minério, ervas e outros recursos.

### Etapa 8 — Profissões

Explicar:

- Alguns mercenários possuem profissão.
- Profissões dão bônus em coletas específicas.
- Um Minerador é melhor em missões de minério, um Lenhador em missões de madeira, etc.

### Etapa 9 — Equipamentos e inventário

Explicar:

- Equipamentos melhoram atributos.
- Alguns itens combinam melhor com certas classes.
- O inventário guarda materiais, armas, armaduras e acessórios.

### Etapa 10 — Dungeons

Explicar:

- Dungeons são desafios mais difíceis.
- Exigem mercenários melhores.
- Podem oferecer recompensas mais raras.

### Etapa 11 — Docas

Explicar:

- As Docas recebem mercantes rotativos.
- Mercantes vendem materiais e alguns itens.
- Evoluir as Docas aumenta opções e chance de produtos melhores.

### Etapa 12 — Progresso idle

Explicar:

- O jogo possui progresso passivo.
- Retorne com frequência para coletar, evoluir e enviar novas missões.
- O progresso offline pode ter limite.

### Etapa 13 — Encerramento

Texto sugerido:

```text
Pronto. Agora você já conhece o básico da guilda. Contrate mercenários, escolha boas missões, colete materiais e evolua sua estrutura para avançar cada vez mais.
```

## Interface do tutorial

O popup deve ter:

- Título.
- Texto da etapa.
- Indicador de progresso, como `3 de 13`.
- Botão `Voltar`.
- Botão `Próximo`.
- Botão `Concluir` na última etapa.
- Botão `Pular tutorial`.
- Confirmação ao pular, se fizer sentido.

## Critérios de aceite

- Exibir convite de tutorial no primeiro acesso.
- Salvar resposta do usuário no banco.
- Não perguntar novamente após concluir ou recusar.
- Permitir avançar páginas.
- Permitir voltar páginas.
- Permitir concluir tutorial.
- Permitir pular tutorial.
- Garantir textos em Português BR.
- Garantir que o tutorial explique os sistemas básicos.
- Garantir que o tutorial não bloqueie o uso do sistema caso o usuário pule.

---

# MVP-034 — Validação final de conteúdo, QA e balanceamento de massa

## Objetivo

Validar se a grande massa de conteúdo criada não gerou buracos de progressão, duplicidades, recompensas quebradas ou itens inacessíveis.

## Checklist de validação

Criar validações automáticas ou relatórios simples para verificar:

- Conteúdo por faixa de nível.
- Conteúdo por raridade.
- Conteúdo por tipo.
- Missões sem recompensa.
- Missões sem drop table.
- Dungeons sem recompensa.
- Itens sem fonte de obtenção.
- Materiais sem uso futuro ou fonte de obtenção.
- Equipamentos sem faixa de nível.
- Equipamentos sem slot.
- Itens com raridade inválida.
- Textos vazios.
- Textos em inglês na camada visual.
- Slugs duplicados.
- Conteúdo fora da faixa 1–350.
- Missões com gold muito alto.
- Missões com XP muito alto.
- Dungeons com recompensa muito baixa.
- Docas vendendo item sem preço.
- Ofertas de Docas sem estoque.
- Profissões sem missão compatível.
- Missões de coleta sem material compatível.

## Relatórios esperados

Criar um comando ou endpoint administrativo, se fizer sentido, para gerar resumo:

```text
Resumo de conteúdo
- Materiais: X
- Equipamentos: X
- Missões: X
- Missões de coleta: X
- Dungeons: X
- Bosses: X
- Profissões: X
- Mercantes: X
- Ofertas possíveis: X
```

Resumo por faixa:

```text
1–20: X missões, X coletas, X dungeons, X itens
21–50: X missões, X coletas, X dungeons, X itens
...
301–350: X missões, X coletas, X dungeons, X itens
```

## Critérios de aceite

- Nenhuma faixa de nível pode ficar sem missões.
- Nenhuma faixa de nível pode ficar sem coleta.
- Nenhuma faixa de nível pode ficar sem dungeon.
- Nenhuma faixa de nível pode ficar sem equipamentos.
- Todo material deve ter ao menos uma fonte de obtenção.
- Todo equipamento deve ter ao menos uma fonte de obtenção.
- Toda profissão deve ter missão compatível.
- Toda oferta de Docas deve ter preço e estoque.
- Nenhum texto visível deve ficar em inglês.
- Seeds devem ser idempotentes.
- O sistema deve continuar funcional após popular a base.

---

# Diretrizes de balanceamento relativo

## Não criar fonte infinita de gold fácil

Docas são dreno de gold.

Mercado/venda de itens gera gold, mas deve ser menor do que o custo de compra nas Docas.

Missões geram gold e XP, mas devem exigir tempo, power e risco.

Dungeons geram melhores drops, mas não devem ser a melhor fonte de gold puro.

## Fontes de materiais

Cada material importante deve ter pelo menos duas fontes:

```text
1. Missão de coleta.
2. Missão comum ou dungeon.
3. Docas, com estoque/preço variável.
```

Materiais raros podem ter apenas:

```text
1. Dungeon/boss.
2. Docas em nível alto.
3. Missão rara.
```

## Fontes de equipamentos

Equipamentos devem vir de:

- Missões comuns.
- Dungeons.
- Bosses.
- Docas com baixa frequência.
- Crafting futuro, se já existir.

## Curva de dificuldade

A dificuldade deve crescer em três eixos:

- Nível recomendado.
- Power recomendado.
- Qualidade de recompensa.

Não criar missões de nível alto com recompensa baixa demais.

Não criar missões fáceis com recompensa alta demais.

## Power recomendado

Se o sistema já tiver fórmula de Power Total, usar essa fórmula.

Caso seja necessário definir ranges relativos, usar lógica aproximada:

| Faixa | Power recomendado baixo | Power recomendado médio | Power recomendado alto |
|---|---:|---:|---:|
| 1–20 | 10 | 25 | 45 |
| 21–50 | 45 | 90 | 150 |
| 51–100 | 150 | 280 | 450 |
| 101–130 | 450 | 650 | 850 |
| 131–200 | 850 | 1.300 | 1.900 |
| 201–250 | 1.900 | 2.500 | 3.200 |
| 251–300 | 3.200 | 4.100 | 5.200 |
| 301–350 | 5.200 | 6.500 | 8.000 |

Se esses valores conflitarem com o balanceamento real do MVP-026, usar os valores reais do sistema e manter apenas a progressão relativa.

---

# Convenção de nomes e slugs

## Nome visual

Nome visual deve conter acento e capitalização correta.

Exemplos:

```text
Madeira de Árvore Anciã
Minério de Mithril
Missão: Patrulha na Estrada da Guilda
Dungeon: Catacumbas da Lua Fraca
```

## Slug técnico

Slug deve ser minúsculo, sem acento, sem espaço.

Exemplos:

```text
madeira_arvore_ancia
minerio_mithril
missao_patrulha_estrada_guilda
dungeon_catacumbas_lua_fraca
```

Se o sistema já usa hífen em vez de underscore, seguir o padrão existente.

## Descrição

Toda descrição deve ser curta e útil.

Evitar textos enormes.

Exemplo:

```text
Madeira resistente coletada em bosques antigos. Usada na criação de arcos, cajados e estruturas da guilda.
```

---

# Ordem final recomendada

Executar nesta ordem:

```text
MVP-027 — Fundação de conteúdo e infraestrutura de seed
MVP-028 — Catálogo massivo de materiais, itens e equipamentos
MVP-029 — Conteúdo massivo de missões do nível 1 ao 350
MVP-030 — Missões de coleta e profissões simples
MVP-031 — Conteúdo massivo de dungeons até o nível 350
MVP-032 — Docas da Guilda e mercantes rotativos
MVP-033 — Tutorial inicial para novos usuários
MVP-034 — Validação final de conteúdo, QA e balanceamento de massa
```

---

# Prompt operacional para o Codex

Use este documento como fonte de verdade para implementar as próximas entregas do Guild Idle Manager.

A última entrega concluída foi o MVP-026. A partir de agora, o foco é popular o jogo com conteúdo massivo.

Prioridades:

1. Criar estrutura segura de seed.
2. Criar materiais e equipamentos em grande volume.
3. Criar missões comuns para todas as faixas até o nível 350.
4. Criar missões específicas de coleta.
5. Criar profissões simples que bonificam coletas.
6. Criar dungeons e bosses em grande volume.
7. Criar Docas como construção/menu de mercantes rotativos.
8. Criar tutorial inicial persistente por usuário.
9. Validar cobertura de conteúdo e ausência de buracos de progressão.

Autonomia autorizada:

- Pode criar nomes, descrições, slugs, drop tables, recompensas e variações em grande volume.
- Pode usar geradores por template, prefixo, sufixo, raridade e faixa de nível.
- Pode criar milhares de registros.
- Pode expandir catálogos além do mínimo.
- Pode ajustar valores relativos caso o balanceamento do MVP-026 indique números melhores.
- Não deve pedir confirmação para cada item, missão ou dungeon.
- Não deve limitar conteúdo por economia de tokens se a geração local por script resolver melhor.
- Deve evitar conteúdo copiado de franquias reais.
- Deve garantir Português BR na interface.

Regra principal:

```text
O jogador não pode ficar sem conteúdo para evoluir.
```
