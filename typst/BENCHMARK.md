# Medições da geração da biblioteca

## Ambiente e método

- Linux x86_64, GCC/cpp 12.2.0 e Typst 0.13.1.
- 188 arquivos de código; 187 listagens no modo padrão e 188 com `--printall`.
- Referência anterior: cópia do gerador antes da otimização, compilada com `g++ -std=c++17 -O2`. Uma execução por modo.
- Gerador otimizado: `g++ -std=c++17 -O2 -pthread`. Mediana de duas execuções por cenário, usando `typst/benchmark.py --repeat 2`.
- Tempos de geração excluem compilação C++ e Typst, medidas separadamente.
- O ambiente é compartilhado e houve variação entre execuções; os números são indicativos, não uma garantia de desempenho.

## Resultados

| Etapa/cenário | Padrão | `--printall` |
| --- | ---: | ---: |
| Geração anterior | 105,39 s | 120,86 s |
| Otimizado, cache frio, 1 trabalhador | 51,27 s | 58,00 s |
| Otimizado, cache quente | 0,065 s | 0,092 s |
| Otimizado, sem cache, 4 trabalhadores | 54,03 s | 61,16 s |

Outras etapas:

- Compilação C++ anterior: **2,82 s**; otimizada: **4,08 s**.
- Compilação Typst do documento padrão: **9,21 s**.
- Alterar um comentário em uma cópia privada de `Grafos/dijkstra.cpp`: **0,158 s** na geração, com **186 acertos e uma falha de cache**. Apenas os 23 hashes desse arquivo foram recalculados.
- Teste completo do shell, executado de outro diretório e direcionando o PDF para `/tmp`: C++ **4,131 s**, geração **0,060 s**, Typst **7,842 s**. O PDF tinha 105 páginas e os PDFs versionados foram preservados.

O ganho de aproximadamente 2× sem cache vem da leitura única, eliminação do arquivo temporário por hash e remoção dos filtros/MD5 externos. Com cache quente, a compilação C++ e o Typst passam a dominar o tempo total; **o fluxo inteiro não leva apenas 0,065 s**.

Quatro trabalhadores não melhoraram o desempenho neste ambiente. Por isso, o padrão continua sendo um; `--jobs N` permite experimentar em outras máquinas.

## Quantidade de trabalho

| Modo | Hashes | Chamadas diretas ao pré-processador, cache frio | Cache quente |
| --- | ---: | ---: | ---: |
| Padrão | 10.096 | 10.096 | 0 |
| `--printall` | 10.306 | 10.306 | 0 |

Há ainda **um processo de identificação do pré-processador por execução**, inclusive com cache quente. As estatísticas contam os processos iniciados diretamente pelo gerador, não descendentes internos do GCC, como `cc1`.

Para cada hash, o pipeline anterior iniciava seis comandos (`sed`, `sed`, `cpp`, `tr`, `md5sum`, `cut`) e um shell. Isso corresponde a 70.672 lançamentos explícitos no modo padrão, sem contar descendentes internos. Agora há apenas uma chamada direta ao pré-processador por hash não encontrado no cache, sem shell intermediário.

## Compatibilidade

Estas referências registram a otimização antes dos ajustes visuais posteriores: remoção da quebra antes de `Extra` e separação dos hashes do destaque de sintaxe. Esses ajustes alteram o markup `.typ` e a paginação, mas não o cálculo nem os valores dos hashes; os SHA-256 abaixo são históricos.

As saídas `.typ` completas do gerador anterior e do otimizado foram comparadas **byte a byte**, nos modos padrão e `--printall`, com e sem cache e com geração paralela. Não houve diferença.

SHA-256 das referências, incluindo a ordem original das seções/listagens:

- Padrão, 377.687 bytes: `b8ef8039a0a31f8168ad7b7eb3ed666d8c956e23d1318ff1f32aa868e25edebe`
- `--printall`, 384.198 bytes: `32a29ab1ae36335297d667683426e45919165284a1a2360674d62f5055fd6a5d`

As verificações adicionais cobrem vetores MD5, filtros antigos, snippets maiores que 10 mil linhas, invalidação/corrupção do cache, falhas de processo, pipes grandes e concorrência. A validação integral foi feita com GCC; Clang não estava disponível. O caminho Clang mantém o comando anterior e desativa o cache persistente para evitar reutilização incorreta de includes/macros de tempo.

## Reproduzir

Na raiz do repositório:

```sh
python3 -m unittest discover -s typst -p 'test_*.py'
python3 typst/benchmark.py --output /tmp/biblioteca-benchmark --repeat 2
```

Para comparar com a versão antiga, salve o `gettypst.cpp` daquela revisão e passe:

```sh
python3 typst/benchmark.py \
  --baseline /tmp/gettypst-anterior.cpp \
  --output /tmp/biblioteca-comparacao --repeat 2
```

O benchmark salva documentos, logs e `results.json` no diretório escolhido, sem alterar os algoritmos ou PDFs versionados. Ele mede Typst somente quando o binário está no `PATH`. A ordem das seções/Extra continua sendo a de leitura dos diretórios, como anteriormente; os SHA-256 acima podem mudar se essa ordem mudar em outro sistema.
