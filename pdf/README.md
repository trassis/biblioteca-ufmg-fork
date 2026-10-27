## Atualizar o PDF da biblioteca (Typst)

A biblioteca usa [Typst](https://typst.app/open-source/) **0.13 ou superior**, sem LaTeX, rubber ou pacotes Typst externos.

Instale o binário `typst` seguindo as [instruções oficiais](https://github.com/typst/typst#installation) (ou baixe-o nas [releases](https://github.com/typst/typst/releases)) e adicione-o ao `PATH`.
No Linux (o gerador usa APIs POSIX e `pipe2`), instale também o compilador C++ e a fonte monoespaçada. No Debian/Ubuntu:

```sh
sudo apt install g++ fonts-dejavu-core
```

O Typst já inclui a fonte Libertinus Serif. A geração dos hashes usa `cpp`, fornecido pelo GCC. O MD5 e os filtros são executados dentro do gerador C++: não é mais necessário iniciar `md5sum`, `sed`, `tr` ou `cut` para cada hash.

Na raiz do repositório, execute:

```sh
bash typst/gettypst.sh
```

O script gera `typst/biblioteca.typ` a partir de `Codigo/` e compila `pdf/biblioteca.pdf`. Ele funciona independentemente do diretório atual e limpa os arquivos temporários. O layout está em `typst/template.typ`: A4 paisagem, duas colunas, índice, títulos e código com destaque de sintaxe e hashes por linha/bloco.

Por padrão, códigos com a flag `noprint` são omitidos. Para incluir todos:

```sh
bash typst/gettypst.sh --printall
```

### Cache, paralelismo e medições

```sh
bash typst/gettypst.sh --stats
bash typst/gettypst.sh --no-cache --stats
bash typst/gettypst.sh --rebuild-cache --stats
bash typst/gettypst.sh --jobs 4 --stats
bash typst/gettypst.sh --cache-dir /tmp/biblioteca-hashes --stats
```

- O cache padrão fica em `typst/.cache/hashes/`, ignorado pelo Git. Ele armazena a listagem com seus hashes por conteúdo de arquivo, não por data de modificação.
- A chave inclui versão do algoritmo/formato, tamanho dos hashes, identidade do pré-processador (caminho, conteúdo do executável e versão), opções e variáveis relevantes de ambiente. Alterar um arquivo invalida apenas sua entrada; arquivos removidos deixam de participar da geração.
- As entradas têm checksum e são gravadas por substituição atômica. Cache ausente ou corrompido é recalculado. Entradas antigas ficam disponíveis até a limpeza manual.
- `--no-cache` não lê nem escreve cache; `--rebuild-cache` ignora as entradas existentes e as recria. Para apagar tudo, execute `rm -rf typst/.cache/hashes` na raiz do repositório.
- `--jobs N` aceita de 1 a 64 trabalhadores, paralelizando por arquivo e preservando a ordem de saída. O padrão é **1**: mais trabalhadores não melhoraram o tempo no ambiente medido e podem sobrecarregar máquinas com poucos recursos.
- `--stats` mostra os tempos de compilação C++, geração e compilação Typst. O gerador também informa arquivos lidos, hashes, processos do pré-processador e acertos/falhas de cache. Mesmo com todos os arquivos em cache, há um processo para identificar a versão do pré-processador; o compilador C++ e o Typst continuam executando normalmente.
- O shell usa GCC. Se o gerador for compilado manualmente com Clang, o fluxo Clang anterior é mantido, mas o cache persistente é desativado: includes e macros de tempo ainda não têm suas dependências rastreadas. O caminho do pré-processador pode ser sobrescrito com `HASH_CPP` (um executável, não um comando com argumentos).

Cada código é lido uma vez e os trechos são enviados ao pré-processador por pipes, sem `tmp.cpp`. Os filtros preservam o comportamento anterior, inclusive o limite de 10 mil linhas por trecho, a remoção de linhas `#w` e de espaços dentro de strings. Falhas do pré-processador agora interrompem a geração, sem armazenar saída parcial no cache.

### Customização

Defina as variáveis de ambiente:

- `TEAMNAME`: nome do time (padrão: `Xerebêlerebébis`)
- `MEMBERS`: integrantes (padrão: `Emanuel Silva, Bruno Monteiro & Rafael Grandsire`)
- `UNIVERSITY`: universidade (padrão: `UFMG`)

```sh
TEAMNAME="Amigos Pessoais" MEMBERS="Laila Melo, Luis Higino & Thiago Assis" UNIVERSITY="HGH" bash typst/gettypst.sh
```

Os valores são texto literal: use `&`, não `\&` como no LaTeX.

Depois da primeira geração, alterações apenas no layout podem ser acompanhadas com:

```sh
typst watch --root . typst/biblioteca.typ pdf/biblioteca.pdf
```

Para personalizar nesse comando, passe `--input 'teamname=Nome do time'`, `--input 'members=Integrantes'` e `--input 'university=Universidade'`. Alterações nos algoritmos exigem executar novamente `gettypst.sh`.

### Testar o gerador

Com Python 3 e as dependências acima instaladas, execute na raiz:

```sh
python3 -m unittest discover -s typst -p 'test_*.py'
```

Os testes verificam compatibilidade com o pipeline anterior, vetores MD5, caracteres especiais, limite de 10 mil linhas, flags, cache/invalidação/corrupção, execução concorrente, pipes grandes e falhas do pré-processador. A compilação Typst é ignorada se o binário não estiver no `PATH`. Os testes de referência ainda usam `sed`, `tr`, `md5sum` e `cut` do coreutils/sed; essas ferramentas não fazem parte do cálculo otimizado.

Para repetir as medições sem alterar `Codigo/` nem os PDFs versionados:

```sh
python3 typst/benchmark.py --output /tmp/biblioteca-benchmark --repeat 2
# Opcional: comparar com uma cópia do gerador anterior.
python3 typst/benchmark.py --baseline /tmp/gettypst-anterior.cpp --output /tmp/biblioteca-comparacao
```

O benchmark salva saídas de referência, logs, tempos separados e `results.json`. Se `typst` estiver no `PATH`, mede também sua compilação. Consulte os resultados iniciais e as decisões em [typst/BENCHMARK.md](../typst/BENCHMARK.md).

## Atualizar o guia teórico (LaTeX)

O conteúdo de `theoretical/` não foi migrado. Sua compilação é independente da biblioteca e continua usando LaTeX:

```sh
sudo apt install texlive-full latexmk
bash latex/getlatex.sh
```

Esse comando gera somente `pdf/theoretical.pdf`. O script mantém as variáveis `TEAMNAME`, `MEMBERS` e `UNIVERSITY`; nesse fluxo, os valores ainda precisam respeitar a sintaxe LaTeX (por exemplo, `\&`).
