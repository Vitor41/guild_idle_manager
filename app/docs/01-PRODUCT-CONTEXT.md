# 01 - Product Context

## Visão geral

Este projeto é um jogo web idle/manager de guilda e mercenários.

O jogador assume o papel de líder de uma guilda. Ele deve contratar mercenários, montar grupos, enviar personagens em missões, coletar recompensas, evoluir a guilda e desbloquear progressões futuras.

O jogo deve misturar duas mecânicas principais:

* gestão de guilda/mercenários;
* idle/incremental game.

## Objetivo do produto

Criar um jogo web simples, escalável e jogável no navegador, começando em ambiente local.

O MVP deve priorizar loop de jogo funcional, isolamento de dados por usuário e estrutura técnica limpa.

## Premissa do jogo

O jogador começa com uma guilda pequena, poucos recursos e mercenários básicos.

A partir disso, ele envia mercenários para contratos e expedições. As missões levam tempo real para terminar. Ao retornar ao jogo, o sistema calcula os resultados, libera recompensas e permite novas decisões.

## Loop principal

O loop principal do jogador é:

1. Entrar no jogo.
2. Ver status da guilda.
3. Coletar recompensas pendentes.
4. Evoluir mercenários, recursos ou estrutura da guilda.
5. Escolher novas missões.
6. Enviar mercenários livres.
7. Sair do jogo.
8. Retornar depois para continuar a progressão.

## Pilares do jogo

### Gestão

O jogador deve tomar decisões sobre:

* quais mercenários contratar;
* quais mercenários enviar para cada missão;
* quais missões priorizar;
* quando assumir risco;
* onde investir recursos;
* como evoluir a guilda.

### Progressão

O jogo deve ter crescimento incremental.

Exemplos:

* mercenários sobem de nível;
* guilda sobe de nível;
* missões melhores são desbloqueadas;
* recursos aumentam;
* recompensas ficam maiores;
* novas possibilidades são liberadas.

### Idle

O jogo não depende de ação contínua do usuário.

Missões continuam contando tempo mesmo com o usuário offline.

O resultado das missões deve ser calculado quando o usuário retorna ao jogo ou acessa uma tela relevante ou ao clicar em "Receber loot" na tela de missões.

### Simplicidade

O MVP não deve tentar ser um RPG completo.

Não haverá combate visual no início.

A simulação será baseada em regras, atributos, chance de sucesso, duração, risco e recompensa.

## Escopo inicial do MVP

O MVP inicial deve conter:

* estrutura base do projeto;
* autenticação;
* usuário logado;
* criação automática ou guiada da guilda;
* isolamento de dados por usuário/guilda;
* mercenários básicos;
* missões disponíveis;
* envio de mercenários para missão;
* cálculo de conclusão idle;
* coleta de recompensas;
* dashboard simples da guilda.

## Fora do escopo inicial

Não implementar no MVP inicial:

* multiplayer em tempo real;
* chat;
* marketplace entre jogadores;
* monetização;
* pagamento;
* ranking avançado;
* guild wars;
* equipamentos complexos;
* crafting;
* mapa visual;
* animação de batalha;
* mobile app nativo;
* worker em background;
* notificações push;
* sistema administrativo avançado.

## Identidade do jogo

O jogo deve ter identidade própria.

Não usar:

* clubes reais;
* jogadores reais;
* marcas reais;
* escudos reais;
* nomes protegidos;
* campeonatos reais;
* assets licenciados.

O universo deve ser fictício e voltado para fantasia medieval/mercenária.

## Direção de produto

O jogo deve nascer pequeno, mas com base técnica suficiente para evoluir.

A prioridade é ter um núcleo funcional e fácil de expandir.

A experiência inicial deve responder rapidamente estas perguntas:

* Qual é minha guilda?
* Quais mercenários eu tenho?
* Quem está livre?
* Quais missões posso fazer?
* Quanto tempo falta?
* O que ganhei?
* O que posso evoluir agora?

## Nome provisório

O nome ainda não está definido.

Durante o desenvolvimento, usar nomes internos genéricos como:

* Guild Idle Manager
* Guild Manager
* Guild Game
* Idle Guild

Não fixar branding definitivo no código neste momento.
