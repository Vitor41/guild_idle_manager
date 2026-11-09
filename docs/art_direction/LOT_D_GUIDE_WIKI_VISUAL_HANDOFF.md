# Lote D — Guia pesquisável, fontes de itens e exportação

**Escopo DA:** ML-025 e ML-026 de `ML-BUGS.md`. Base visual: `app/templates/guide/index.html`, `.guide-index`, `.guide-section` e tokens Sala de Comando. Conteúdo, chances, requisitos e disponibilidade vêm da fonte canônica definida pelo DEV; este handoff trata da apresentação.

## Navegação e hierarquia

Adicionar **Equipamentos e Materiais** ao índice horizontal existente do Guia, com âncora que chega ao título visível abaixo da barra superior. A nova seção usa o mesmo número/título, borda e superfície dos demais capítulos. Dentro dela, um segundo índice discreto de fontes — **Missões, Masmorras, Chefes, Coleta, Docas, Desmontagem** e outras fontes especiais ativas — conduz às subseções sem criar uma página paralela. O índice secundário mantém chips de pelo menos 40 px, foco de 3 px e rolagem horizontal em 420 px; `aria-current="location"` indica a seção ativa somente quando conhecida. Nome da fonte e natureza da obtenção aparecem em texto, não apenas em cor ou ícone.

## Busca global e filtros da seção

Colocar a **Busca no Guia** logo após o hero e antes do índice principal, com label visível, campo e botão **Buscar**. Enter e botão executam a mesma busca sobre todo o conteúdo do Guia, inclusive seções fora da área de fontes. Ao encontrar, rolar até a primeira ocorrência, manter o título da seção visível e aplicar destaque de fundo dourado suave com contraste de texto preservado; foco vai ao resultado ou ao título, de modo que teclado/leitor de tela saibam onde a navegação terminou. Uma nova busca remove o destaque anterior. Mostrar mensagem curta “Nenhum resultado para [termo]” em `role="status"`, com campo e Guia ainda utilizáveis. Para termo vazio, indicar como pesquisar sem simular resultado. Evitar destaque piscante e rolagem animada obrigatória; respeitar movimento reduzido.

Na seção **Equipamentos e Materiais**, manter filtros locais separados da busca global: **nome do item**, **família/tipo**, **tier/faixa** e **fonte**. Identificar o recorte ativo e oferecer **Limpar filtros**. O filtro por nome não deve assumir que a busca global está limitada à seção. Em 420 px, controles empilham; labels permanecem visíveis, selects e botão ocupam largura legível. Atualização de resultados anuncia apenas contagem/estado, sem narrar toda a lista. Se não houver itens no recorte: “Nenhum item corresponde aos filtros” e ação para limpá-los. Se a fonte de dados falhar: mensagem de indisponibilidade e tentativa de recarga, distinguível de resultado vazio.

## Fontes e chances

Agrupar resultados por **conteúdo ou atividade concreta** que concede o item. Uma linha/cartão mostra ícone de grupo 48–64 px, nome completo limpo, raridade/tier quando aplicável, requisito, origem e quantidade mínima–máxima quando houver. A coluna **Chance** precisa dizer a que evento se refere: “chance por entrada de drop”, “chance de unidade extra por ciclo”, “compra; sem chance de drop” ou “resultado de desmontagem”, conforme o dado real. Não usar uma porcentagem isolada que pareça garantia de obter todos os itens. Docas são comércio, com condição de oferta/rotação, nunca drop. Material sem fonte acessível aparece como **“Sem fonte disponível”** em estado de conteúdo, sem probabilidade inventada; a correção do catálogo pertence ao DEV.

Em desktop, usar tabela semântica para listas densas com cabeçalhos **Fonte/atividade, Item, Requisito, Chance, Quantidade** e grupos identificados por título; detalhes podem expandir condições sem esconder o nome ou a chance. Em 420 px/zoom 200%, cada linha pode virar card de pares rótulo–valor, preservando a associação entre atividade e item. Números têm algarismos tabulares. Sprites existentes do manifesto (`item-book`, `item-quest-scroll`, famílias `material-*`, `item-*`) bastam; não gerar arte nova nem colocar texto essencial em bitmap.

## Exportação Markdown e estados

Ao lado da busca, ou em uma linha de ações logo abaixo, inserir **Baixar Guia em Markdown** como botão secundário com descrição curta “Conteúdo atual do Guia, em PT-BR”. Em janela estreita, fica em linha própria. Ao iniciar, mostrar “Preparando arquivo…” com indicador discreto e botão temporariamente ocupado; no sucesso, confirmar “Download iniciado” sem substituir o conteúdo do Guia. Em falha, mostrar motivo legível e **Tentar novamente**. Nome do arquivo, versão e data ficam no próprio `.md` e podem aparecer na confirmação se o servidor os fornecer. A interface não monta um texto paralelo nem mistura dados privados de campanha no arquivo.

## Aceite visual

Conferir âncoras e Voltar do navegador, busca em outra seção por Enter/botão, buscas sucessivas, termo sem resultado, filtros combinados/limpos, fonte sem itens, falha de carga, chance com unidade/contexto, download/falha, teclado, leitor de tela, 420 px, zoom 200% e movimento reduzido. O DEV deve comprovar que tela e exportação consomem a mesma fonte de conteúdo e entregar branch/hash e evidência por critério conforme `AGENTS.md`; o usuário fará o aceite visual do aplicativo.
