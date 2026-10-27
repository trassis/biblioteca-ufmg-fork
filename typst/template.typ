// Layout da biblioteca; não depende de pacotes externos.
// Cor dos comentários no tema padrão de destaque de sintaxe do Typst.
#let comment-color = rgb("#8a8a8a")

#let listing(source, hashed: false) = {
  let lines = source.split("\n")
  let hashes = lines.map(line => {
    if hashed and line.match(regex("^[0-9a-f]{3} ")) != none {
      line.slice(0, 3)
    } else {
      none
    }
  })
  // Destaque apenas o código, sem deixar os hashes interferirem no lexer.
  let code = lines.enumerate().map(((index, line)) => {
    if hashes.at(index) != none { line.slice(4) } else { line }
  }).join("\n")
  show raw.line: line => {
    let hash = hashes.at(line.number - 1, default: none)
    if hash != none { text(fill: comment-color, hash + " ") }
    line.body
  }
  raw(code, block: true, lang: "cpp")
}

#let biblioteca(body) = {
  let team = sys.inputs.at("teamname", default: "Xerebêlerebébis")
  let members = sys.inputs.at("members", default: "Emanuel Silva, Bruno Monteiro & Rafael Grandsire")
  let university = sys.inputs.at("university", default: "UFMG")

  set document(title: team + " — " + university, author: members)
  set text(font: "Libertinus Serif", size: 10pt, lang: "pt")
  set page(
    paper: "a4",
    flipped: true,
    columns: 2,
    margin: (left: 0.5cm, right: 0.5cm, top: 1cm, bottom: 1.5cm),
    numbering: "1",
  )
  set columns(gutter: 10pt)
  set par(leading: 0.5em)
  set heading(numbering: "1.1")
  show heading.where(level: 1): set text(size: 14pt)
  show heading.where(level: 2): set text(size: 11pt)
  set raw(tab-size: 4)
  show raw: set text(font: "DejaVu Sans Mono", size: 7pt)
  // Permite quebrar listagens longas entre colunas e páginas.
  show raw.where(block: true): it => block(
    breakable: true,
    width: 100%,
    text(hyphenate: false, overhang: false, it),
  )

  align(center)[
    #text(size: 20pt, weight: "bold", team) \
    #text(size: 14pt, university) \
    #members \
    #datetime.today().display("[day]/[month]/[year]")
  ]
  outline(title: [Índice])
  body
}
