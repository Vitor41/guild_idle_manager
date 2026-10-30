# Instalador Desktop DEV — entrega para validação do usuário (30/10/2026)

**Estado estático:** PASS. O único artefato mantido em `dist` é `C:\Users\vitor\Guild Idle Manager\App GIM\dist\GuildIdleManager-DEV-Setup.exe`.

- Canal: **DEV**; versão declarada pela aplicação: `0.1.0` (`app/main.py`); schema SQLite `6`; catálogo `3`. O bundle não declara um file version separado.
- Origem: commit `8b5f21a` com alterações locais pendentes (árvore suja: `true`).
- Setup: `GuildIdleManager-DEV-Setup.exe` — 60,047,360 bytes — SHA-256 `735CC153A82509D632169B9E47DEE11C5181C536D2135FEF8D272F3DFB96BFD0`.
- O ZIP usado dentro do Setup foi auditado antes da limpeza: 60,473,770 bytes — SHA-256 `214D7AB667A5C449C89D21681763C4124AD176070A31EDEA30E8A5A9D6A97710`. A cópia avulsa foi removida para deixar apenas o instalador final.
- Bundle: 896 arquivos / 83,029,851 bytes. Pacote ZIP: 898 arquivos / 83,044,080 bytes.
- ZIP CRC: `PASS`; hashes do ZIP iguais aos arquivos do pacote staged: `True`.
- Assinatura PE `MZ`: `True`; arquivos runtime obrigatórios ausentes: 0; 7 arquivos-chave do bundle conferem byte a byte com a origem atual.

O Setup foi gerado pelo IExpress a partir do ZIP e do script `Install-Desktop-Dev.ps1`. O primeiro build demorou além do limite de espera de 90 s embora tenha materializado o Setup logo depois; o build script agora aguarda até 300 s e o segundo build terminou com sucesso. Nenhum Setup foi executado, nenhuma GUI aberta e nenhum save/dado real acessado.

A auditoria confirmou estaticamente o CRC do ZIP, a correspondência de hash de todos os membros do pacote e os templates, recursos de evolução e migration listados no manifesto JSON. A instalação e validação visual ficam para o usuário.

Build reproduzível: `powershell -ExecutionPolicy Bypass -File scripts/build_desktop_dev.ps1` (gera uma pasta nova sob `dist/staging`). Para instalar, execute `dist\GuildIdleManager-DEV-Setup.exe`. O instalador inclui o bundle; não há ZIP separado.

Inventário completo e hashes: [JSON do candidato](desktop_dev_final_candidate_2026-10-30.json).
