// Layout da biblioteca; não depende de pacotes externos.
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
