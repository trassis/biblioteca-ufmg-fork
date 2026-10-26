## Atualizar o PDF da biblioteca (Typst)

A biblioteca usa [Typst](https://typst.app/open-source/) **0.13 ou superior**, sem LaTeX, rubber ou pacotes Typst externos.

Instale o binário `typst` seguindo as [instruções oficiais](https://github.com/typst/typst#installation) (ou baixe-o nas [releases](https://github.com/typst/typst/releases)) e adicione-o ao `PATH`.
No Debian/Ubuntu, instale também o compilador C++, as ferramentas de hash e a fonte monoespaçada:

```sh
sudo apt install g++ coreutils fonts-dejavu-core
```

O Typst já inclui a fonte Libertinus Serif. A geração dos hashes usa `cpp`, fornecido pelo GCC, e `md5sum`, do coreutils.

Na raiz do repositório, execute:

```sh
bash typst/gettypst.sh
```

O script gera `typst/biblioteca.typ` a partir de `Codigo/` e compila `pdf/biblioteca.pdf`. Ele funciona independentemente do diretório atual e limpa os arquivos temporários. O layout está em `typst/template.typ`: A4 paisagem, duas colunas, índice, títulos e código com destaque de sintaxe e hashes por linha/bloco.

Por padrão, códigos com a flag `noprint` são omitidos. Para incluir todos:

```sh
bash typst/gettypst.sh --printall
```

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

Os testes verificam hashes, títulos/códigos literais, `noprint`, `--printall` e compilação Typst (esta última é ignorada se o binário não estiver no `PATH`).

## Atualizar o guia teórico (LaTeX)

O conteúdo de `theoretical/` não foi migrado. Sua compilação é independente da biblioteca e continua usando LaTeX:

```sh
sudo apt install texlive-full latexmk
bash latex/getlatex.sh
```

Esse comando gera somente `pdf/theoretical.pdf`. O script mantém as variáveis `TEAMNAME`, `MEMBERS` e `UNIVERSITY`; nesse fluxo, os valores ainda precisam respeitar a sintaxe LaTeX (por exemplo, `\&`).
