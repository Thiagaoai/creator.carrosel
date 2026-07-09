# Keychain PLJ CARPENTRY — Setup completo para Bambu Studio

Peça de 2 cores: **base preta** (disco + argola) e **logo amarelo em alto relevo**
(serra, martelo + chave, barra e o nome). Modelada do zero para eliminar os
problemas do arquivo anterior:

- **Linhas atrás do nome** → o logo agora é UM único sólido (união booleana), sem
  contornos sobrepostos. Nada "vaza" por trás das letras.
- **Z-fighting / faces piscando** → o relevo penetra 0,04 mm dentro da base, então
  as duas peças se fundem no fatiamento sem superfícies coplanares.
- **Alto relevo** → 1,2 mm de altura (6 camadas de 0,2 mm): destaca bem e não
  descola.
- **Costas "couro"** → a parte de trás é 100% plana e imprime virada para baixo na
  chapa **Textured PEI**: a textura da chapa dá o acabamento fosco tipo couro e
  esconde marcas, cicatrizes de seam e pequenos defeitos.

## Arquivos

| Arquivo | Uso |
| --- | --- |
| `keychain_base_black.stl` | Corpo preto (importar no Bambu Studio) |
| `keychain_logo_yellow.stl` | Logo amarelo em relevo (importar junto) |
| `plj_keychain.scad` | Fonte paramétrica (OpenSCAD) — mude tamanho, texto, alturas |
| `plj_logo_inkscape.svg` | Arte 2D do logo para editar no Inkscape |
| `plj_base_inkscape.svg` | Contorno 2D da base para editar no Inkscape |
| `preview_top.png` / `preview_3d.png` | Conferência visual |

Dimensões: **50 mm de diâmetro** (66,3 mm com a argola), 2,4 mm de base,
3,6 mm de altura total. Furo da argola: 6 mm (anel chaveiro padrão).

## Passo a passo no Bambu Studio

### 1. Importar

1. `Arquivo → Importar` e selecione **os dois STLs ao mesmo tempo**
   (`keychain_base_black.stl` + `keychain_logo_yellow.stl`).
2. O Bambu Studio pergunta: *"Load these files as a single object with multiple
   parts?"* → responda **SIM (Yes)**. Isso é obrigatório — os dois arquivos já
   compartilham a mesma origem e se encaixam sozinhos.
3. Na árvore de objetos vão aparecer as duas *parts* dentro de um objeto só.

> Se importar um de cada vez, as peças chegam separadas na mesa e desalinhadas.
> Se isso acontecer, apague tudo e importe os dois juntos.

### 2. Cores (AMS ou troca manual)

**Com AMS:**
1. Carregue PLA preto e PLA amarelo/dourado no AMS.
2. Clique na part `keychain_base_black` → atribua o **filamento preto**.
3. Clique na part `keychain_logo_yellow` → atribua o **filamento amarelo**.

**Sem AMS (troca manual — mais econômico, zero purga):**
1. Fatie com um filamento só.
2. Na barra deslizante de camadas (lado direito da pré-visualização), suba até
   **Z = 2,4 mm** (fim da camada 12 com camadas de 0,2 mm) — é exatamente onde o
   preto termina e o amarelo começa.
3. Clique com o botão direito no marcador da camada → **"Add filament change"**
   (ou "Pause" e troque na mão). A impressora pausa, você troca preto → amarelo
   e continua. Como a divisa de cor é plana, o resultado fica perfeito.

### 3. Setup de impressão (os valores que importam)

| Parâmetro | Valor | Por quê |
| --- | --- | --- |
| Chapa | **Textured PEI Plate** | O verso vira "couro" e esconde marcas. NÃO use a lisa/fria para esse efeito |
| Altura de camada | **0,2 mm** (ou 0,12 para letras ainda mais nítidas) | 12 camadas de base + 6 de relevo |
| Primeira camada | 0,2 mm, velocidade padrão | Contato total do disco — adesão sobra |
| Paredes | **3** | Letras pequenas ficam sólidas |
| Preenchimento | 15 % gyroid | Peça fina, quase não tem infill |
| Suporte | **DESLIGADO** | Nada em balanço |
| Brim | Desligado | O disco já tem área de sobra |
| Seam / costura | **Rear** (traseira) ou **Aligned** | Costura fica escondida num ponto só |
| Filamento | PLA / PLA Matte | Matte disfarça ainda mais qualquer marca |

### 4. IRONING (passar ferro) — cuidado com o setup

O ironing deixa o topo do relevo amarelo liso e brilhante, mas configurado
errado ele arrasta plástico e cria fios. Use exatamente assim:

- **Ironing Type:** `Topmost surface` (SOMENTE a superfície mais alta —
  **nunca** `All solid surfaces`, senão ele passa ferro dentro da peça e nas
  bordas do relevo, criando rebarbas).
- **Ironing flow:** `10 %`
- **Ironing speed:** `30 mm/s`
- **Ironing line spacing:** `0,1 mm`

Com `Topmost surface`, o topo preto exposto (ao redor do logo) e o topo amarelo
das letras são alisados cada um com a própria cor — sem contaminação.

> O ironing NÃO afeta o verso da peça: o acabamento de trás vem 100 % da chapa
> texturizada. Não tente "passar ferro" na primeira camada.

### 5. Conferência antes de fatiar (checklist)

- [ ] Peça deitada com o **logo para cima** (verso no Z=0 — já vem assim, não gire nada).
- [ ] As duas parts dentro de UM objeto, cada uma com sua cor.
- [ ] Na pré-visualização fatiada, arraste o slider e confira: camadas 1–12
      pretas, 13–18 amarelas, letras do nome legíveis e separadas.
- [ ] Suporte desligado, brim desligado, chapa Textured PEI selecionada.

## Editando o design

### No Inkscape (arte 2D)

Abra `plj_logo_inkscape.svg` — a arte está no tamanho real (mm). Você pode
ajustar formas e depois:

- **Caminho → Unir (Ctrl +)** em tudo que for amarelo antes de exportar — é isso
  que evita as "linhas atrás do nome" (contornos sobrepostos viram furos ou
  riscos no fatiador);
- Importar o SVG direto no Bambu Studio (`Adicionar → SVG`) e extrudar com
  1,2 mm sobre a base, **ou** substituir o desenho dentro do `.scad`.

### No OpenSCAD (paramétrico — recomendado)

Abra `plj_keychain.scad`. Tudo é variável no topo do arquivo:

- `disc_r = 25;` → raio do disco (mude para 27,5 se quiser 55 mm)
- `relief_h = 1.2;` → altura do alto relevo
- `text_string = "PLJ CARPENTRY";` → o nome
- `loop_hole_r = 3.0;` → furo da argola

Para regerar os STLs:

```bash
openscad -o keychain_base_black.stl  -D 'part="base"' plj_keychain.scad
openscad -o keychain_logo_yellow.stl -D 'part="logo"' plj_keychain.scad
```

A fonte usada é a **Anton** (Google Fonts, gratuita) — instale-a no sistema
antes de regerar, senão o OpenSCAD troca por outra fonte.

## Por que o arquivo antigo falhava (resumo técnico)

1. **Contornos duplicados/sobrepostos atrás do texto** → o fatiador gera
   "linhas" e paredes fantasma. Corrigido unindo toda a arte num único caminho.
2. **Logo e base com faces exatamente coplanares (Z idêntico)** → z-fighting e
   camadas trocando de cor aleatoriamente. Corrigido afundando o relevo 0,04 mm
   na base.
3. **Traços finos demais para o bico de 0,4 mm** → letras com ~1,1 mm de haste
   neste modelo (2,5× a largura de extrusão), imprimem sólidas.
4. **Verso marcado** → resolvido imprimindo o verso direto na chapa texturizada
   (efeito couro) + PLA fosco + costura alinhada atrás.
